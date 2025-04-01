import pytest
from omegaconf import OmegaConf
from contextlib import contextmanager

from bbot_server.config import BBOT_SERVER_CONFIG
from bbot_server.message_queue import MessageQueue

from ..conftest import *


class BaseAppletTest:
    log = logging.getLogger("bbot.server.test")

    config_overrides = {}

    needs_api = False
    needs_agent = False
    needs_watchdog = False

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

    async def test_applet_run(self, bbot_server, bbot_events, bbot_server_config):
        """
        The main test function that runs each of the individual applet tests.
        """
        self.log = logging.getLogger(f"bbot.server.test.{self.__class__.__name__.lower()}")
        self.bbot_server_config = bbot_server_config
        self.bbot_server = await bbot_server(
            config_overrides=self.config_overrides,
            needs_api=self.needs_api,
            needs_agent=self.needs_agent,
            needs_watchdog=self.needs_watchdog,
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
            await asyncio.sleep(2.0)

            # run the first test after scan #1 has been ingested
            with self.handle_errors("running tests after first scan"):
                await self.after_scan_1()

            # insert events from the second scan
            with self.handle_errors("inserting data from second scan"):
                for event in self.scan2_events:
                    await self.bbot_server.insert_event(event)
            await asyncio.sleep(2.0)

            # run test after scan #2 has been ingested
            with self.handle_errors("running tests after second scan"):
                await self.after_scan_2()

            # archive old events (from the first scan)
            with self.handle_errors("running archive task"):
                await self.bbot_server.archive_old_events()
            # wait for the archive task to finish
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
        Tail event and asset activities and store them for use in the tests
        """

        async def tail_events():
            try:
                agen = self.bbot_server.tail_events(n=10)
                async for event in agen:
                    event_messages.append(event)
                with suppress(BaseException):
                    await agen.aclose()
            except Exception:
                import traceback

                self.log.critical(traceback.format_exc())
                raise

        async def tail_activities():
            try:
                agen = self.bbot_server.tail_assets(n=10)
                async for activity in agen:
                    self.log.info(f"{activity.type} - {activity.description}")
                    asset_messages.append(activity)
                with suppress(BaseException):
                    await agen.aclose()
            except Exception:
                import traceback

                self.log.critical(traceback.format_exc())
                raise

        event_tail_task = asyncio.create_task(tail_events())
        asset_tail_task = asyncio.create_task(tail_activities())

        await asyncio.sleep(0.2)

        return event_tail_task, asset_tail_task

    @contextmanager
    def handle_errors(self, test_description):
        try:
            yield
        except BaseException as e:
            raise Exception(f"{self.__class__.__name__} failed while {test_description}: {e}")
