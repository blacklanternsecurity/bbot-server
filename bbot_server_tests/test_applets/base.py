import pytest
from contextlib import contextmanager

from ..conftest import *


class BaseAppletTest:
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

    async def test_applet_run(self, bbot_server, bbot_events):
        """
        The main test function that runs each of the individual applet tests.
        """
        self.log = logging.getLogger(f"bbot_server.test.{self.__class__.__name__.lower()}")
        self.bbot_server = bbot_server
        self.scan1_events = bbot_events[0]
        self.scan2_events = bbot_events[1]

        try:
            with self.handle_errors("setting up tasks to tail events and assets"):
                self.setup_activities()

            with self.handle_errors("running pre-scan tests"):
                await self.setup()

            with self.handle_errors("inserting data from first scan"):
                for event in self.scan1_events:
                    await self.bbot_server.insert_event(event)
            await asyncio.sleep(0.5)

            with self.handle_errors("running tests after first scan"):
                await self.after_scan_1()

            with self.handle_errors("inserting data from second scan"):
                for event in self.scan2_events:
                    await self.bbot_server.insert_event(event)
            await asyncio.sleep(0.5)

            with self.handle_errors("running tests after second scan"):
                await self.after_scan_2()

            # with self.handle_errors("archiving first scan"):
            #     scan_id = applet_test.scan1_events[0].data["id"]
            #     await self.bbot_server.archive_scan(scan_id)
            # await asyncio.sleep(.5)

            with self.handle_errors("running tests after archiving first scan"):
                await self.after_archive()

        finally:
            await self.cleanup()
            await self.bbot_server.cleanup()
            for task in [self.event_tail_task, self.asset_tail_task]:
                task.cancel()
                with suppress(BaseException):
                    await task

    def setup_activities(self):
        """
        Tail event and asset activities and store them for the convenience of the applet tests
        """
        self.event_messages = []
        self.asset_messages = []

        async def tail_events():
            agen = self.bbot_server.tail_events()
            async for event in agen:
                self.event_messages.append(event)
            await agen.aclose()

        async def tail_assets():
            agen = self.bbot_server.tail_assets()
            async for asset in agen:
                self.asset_messages.append(asset)
            await agen.aclose()

        self.event_tail_task = asyncio.create_task(tail_events())
        self.asset_tail_task = asyncio.create_task(tail_assets())

    @contextmanager
    def handle_errors(self, test_description):
        try:
            yield
        except BaseException as e:
            raise pytest.fail(f"{self.__class__.__name__} failed while {test_description}: {e}")
