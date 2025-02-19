import pytest
from omegaconf import OmegaConf
from contextlib import contextmanager

from ..conftest import *


class BaseAppletTest:
    log = logging.getLogger("bbot_server.test")

    config_overrides = {}

    async def setup(self):
        """
        This test is executed before any scans have been run.
        """
        pass

    async def after_scan_1(self):
        """
        This test is executed after the first scan has been run.
        """
        pass

    async def after_scan_2(self):
        """
        This test is executed after the second scan has been run.
        """
        pass

    async def after_archive(self):
        """
        This test is executed after the first scan has been archived.
        """
        pass

    async def cleanup(self):
        """
        This test is executed after all the tests are finished.
        """
        pass

    @pytest.fixture
    def bbot_server_config(self):
        return OmegaConf.merge(BBOT_SERVER_CONFIG, self.config_overrides)

    @pytest_asyncio.fixture(scope="function")
    async def bbot_server_http(self, bbot_server_config):
        import httpx
        import uvicorn
        from uvicorn.server import logger
        from bbot_server.api import make_server_app

        server_app = make_server_app(config=bbot_server_config)

        server = uvicorn.Server(uvicorn.Config(server_app, host="127.0.0.1", port=8807, log_level="debug"))
        api = asyncio.create_task(server.serve())

        # Wait for the server to be ready
        async with httpx.AsyncClient() as client:
            url = "http://localhost:8807/v1/assets/"
            while True:
                try:
                    response = await client.get(url)
                    if response.status_code == 200:
                        break
                except httpx.RequestError as e:
                    logger.debug(f"Error connecting to bbot-server: {e}")
                await asyncio.sleep(0.2)

        yield "http://127.0.0.1:8807"

        # server.should_exit = True
        server.force_exit = True
        await server.shutdown()
        await asyncio.sleep(0.5)
        api.cancel()
        with suppress(BaseException):
            await api

    @pytest_asyncio.fixture(params=[{"interface": "python"}, {"interface": "http"}])
    # @pytest_asyncio.fixture
    async def bbot_server(self, request, mongo_cleanup, bbot_server_http, bbot_server_config):
        from bbot_server import BBOTServer
        from bbot_server.config import BBOT_SERVER_CONFIG
        from bbot_server.watchdog.worker import WatchdogWorker

        kwargs = dict(request.param)
        # kwargs = {}
        kwargs.update({"config": bbot_server_config})

        bbot_server = BBOTServer(**kwargs)
        print(bbot_server.config)
        watchdog = WatchdogWorker(bbot_server)
        await watchdog.start()

        yield bbot_server

        await watchdog.stop()

    async def test_applet_run(self, bbot_server, bbot_events):
        """
        The main test function that runs each of the individual applet tests.
        """
        self.log = logging.getLogger(f"bbot_server.test.{self.__class__.__name__.lower()}")
        self.bbot_server = bbot_server
        await self.bbot_server.setup()

        self.scan1_events = bbot_events[0]
        self.scan2_events = bbot_events[1]

        try:
            with self.handle_errors("setting up tasks to tail events and assets"):
                self.event_messages = []
                self.asset_messages = []
                self.event_tail_task, self.asset_tail_task = self.setup_activities(
                    self.event_messages, self.asset_messages
                )

            # before any scans start
            with self.handle_errors("running pre-scan tests"):
                await self.setup()
            await asyncio.sleep(0.5)

            # insert events from the first scan
            with self.handle_errors("inserting data from first scan"):
                for event in self.scan1_events:
                    await self.bbot_server.insert_event(event)
            await asyncio.sleep(1)

            # run the first test after scan #1 has been ingested
            with self.handle_errors("running tests after first scan"):
                await self.after_scan_1()

            # insert events from the second scan
            with self.handle_errors("inserting data from second scan"):
                for event in self.scan2_events:
                    await self.bbot_server.insert_event(event)
            await asyncio.sleep(1)

            # run test after scan #2 has been ingested
            with self.handle_errors("running tests after second scan"):
                await self.after_scan_2()

            # archive old events (from the first scan)
            with self.handle_errors("running archive task"):
                await self.bbot_server.archive_old_events()
            await asyncio.sleep(1)

            # final test - after archiving
            with self.handle_errors("running tests after archiving first scan"):
                await self.after_archive()

        finally:
            await self.cleanup()
            await self.bbot_server.cleanup()
            for task in [self.event_tail_task, self.asset_tail_task]:
                task.cancel()
                with suppress(BaseException):
                    await task

    def setup_activities(self, event_messages, asset_messages):
        """
        Tail event and asset activities and store them for the convenience of the applet tests
        """

        async def tail_events():
            agen = self.bbot_server.tail_events()
            async for event in agen:
                event_messages.append(event)
            with suppress(BaseException):
                await agen.aclose()

        async def tail_assets():
            agen = self.bbot_server.tail_assets()
            async for asset in agen:
                asset_messages.append(asset)
            with suppress(BaseException):
                await agen.aclose()

        event_tail_task = asyncio.create_task(tail_events())
        asset_tail_task = asyncio.create_task(tail_assets())

        return event_tail_task, asset_tail_task

    @contextmanager
    def handle_errors(self, test_description):
        # self.log.info(test_description)
        try:
            yield
        except BaseException as e:
            raise Exception(f"{self.__class__.__name__} failed while {test_description}: {e}")
