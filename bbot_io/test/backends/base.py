import pytest
import asyncio
import logging
from copy import copy
from bbot_io.test.applets import applet_tests


log = logging.getLogger("bbot.test.modules")


class IOTestBase:
    log = logging.getLogger("bbot.io")

    needs_server = False

    from ._gen_scan_data import gen_scan_data, patch_scan

    class Fixtures:
        def __init__(self, monkeypatch):
            self.monkeypatch = monkeypatch

    @property
    def scan1_events(self):
        return [copy(e) for e in self._scan1_events]

    @property
    def scan2_events(self):
        return [copy(e) for e in self._scan2_events]

    @pytest.mark.asyncio
    async def test_module_run(self, monkeypatch):
        """
        This is the main test function

        It runs once for every backend, and tests every applet.
        """

        self.fixtures = self.Fixtures(monkeypatch)

        # start the BBOT web server if needed
        if self.needs_server:
            import multiprocessing
            from bbot_io.server import run_server

            kwargs = {"database": "/tmp/.bbotio_test/test.db", "uvicorn_options": {"port": 7777}}
            # start bbot server in a separate process
            proc = multiprocessing.Process(target=run_server, daemon=True, args=("sqlite",), kwargs=kwargs)
            proc.start()

            # allow some time for the server to start
            await asyncio.sleep(3)

        self._scan1_events, self._scan2_events = await self.gen_scan_data()

        # test applets
        for applet_name, applet_test in applet_tests.items():

            # instantiate io module
            self.io = await self.setup()
            await self.io.setup()

            log.info(f"Testing applet: {applet_name}")
            # test events
            await self.ensure_empty()
            await applet_test(self)

        # clean up
        await self.ensure_empty()

    async def ensure_empty(self):
        # clear database
        await self.io.drop_database()

        # make sure everything is empty
        await self.assert_empty()

    async def assert_empty(self):
        # scans
        scans = await self.io.get_scans()
        assert scans == []
        # events
        events = await self.io.get_events()
        assert events == []
        # subdomains
        subdomains = await self.io.get_subdomains()
        assert subdomains == [], f"subdomains: {subdomains}"
        # targets
        targets = await self.io.get_targets()
        assert targets == [], f"targets: {targets}"

    async def setup(self):
        from bbot_io import BBOT_IO

        return BBOT_IO(self.backend, **self.kwargs)
