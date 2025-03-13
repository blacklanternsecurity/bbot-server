import pytest
from omegaconf import OmegaConf
from contextlib import contextmanager

from bbot_server.config import BBOT_SERVER_CONFIG

from ..conftest import *


class BaseAppletTest:
    log = logging.getLogger("bbot.server.test")

    config_overrides = {}

    needs_agent = False

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
        self.log = logging.getLogger(f"bbot.server.test.{self.__class__.__name__.lower()}")
        self.bbot_server, self.watchdog, self.agent = await bbot_server(
            config_overrides=self.config_overrides, needs_agent=self.needs_agent
        )

        self.scan1_events = bbot_events[0]
        self.scan2_events = bbot_events[1]

        try:
            with self.handle_errors("setting up tasks to tail events and assets"):
                self.event_messages = []
                self.asset_messages = []
                self.event_tail_task, self.asset_tail_task = await self.setup_activities(
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
            with suppress(Exception):
                for task in [self.event_tail_task, self.asset_tail_task]:
                    task.cancel()
                    with suppress(BaseException):
                        await task

    async def setup_activities(self, event_messages, asset_messages):
        """
        Tail event and asset activities and store them for the convenience of the applet tests
        """

        async def tail_events():
            try:
                agen = self.bbot_server.tail_events()
                async for event in agen:
                    event_messages.append(event)
                with suppress(BaseException):
                    await agen.aclose()
            except Exception:
                import traceback

                self.log.critical(traceback.format_exc())
                raise

        async def tail_assets():
            try:
                agen = self.bbot_server.tail_assets()
                async for asset in agen:
                    asset_messages.append(asset)
                with suppress(BaseException):
                    await agen.aclose()
            except Exception:
                import traceback

                self.log.critical(traceback.format_exc())
                raise

        event_tail_task = asyncio.create_task(tail_events())
        asset_tail_task = asyncio.create_task(tail_assets())

        return event_tail_task, asset_tail_task

    @contextmanager
    def handle_errors(self, test_description):
        try:
            yield
        except BaseException as e:
            raise Exception(f"{self.__class__.__name__} failed while {test_description}: {e}")
