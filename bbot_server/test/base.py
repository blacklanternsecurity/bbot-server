import pytest
import logging
import inspect
from bbot_server.test.applets import applet_tests


log = logging.getLogger("bbot.test.modules")
# sqlalchemy debugging
# logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)


class IOTestBase:
    log = logging.getLogger("bbot.server")

    needs_server = False

    class Fixtures:
        def __init__(self, monkeypatch):
            self.monkeypatch = monkeypatch

    @pytest.mark.asyncio
    async def test_applets(self, monkeypatch, http_server, gen_scan_data):
        """
        This is the main test function

        It runs once for every backend, and tests every applet.
        """

        self.fixtures = self.Fixtures(monkeypatch)

        # instantiate io module
        self.io = await self.setup()
        await self.io.setup()

        # test applets
        for applet_name, applet_test in applet_tests.items():
            log.info(f"Testing applet: {applet_name}")
            # test events
            await self.ensure_empty()
            await applet_test(self, gen_scan_data)

        # clean up
        await self.ensure_empty()

    @pytest.mark.asyncio
    async def test_synchronous(self, monkeypatch, http_server, gen_scan_data):
        self.fixtures = self.Fixtures(monkeypatch)

        scan1_events, scan2_events = await gen_scan_data()

        self.io = await self.setup(synchronous=True)

        # import asyncio
        # for i in range(100):
        #     print(self.io.setup)
        #     await asyncio.sleep(.1)

        # Assert that the self.io.setup() call is synchronous
        assert not inspect.iscoroutinefunction(self.io.setup), f"{self.io.setup} method should be synchronous"

        self.io.drop_database()

        for event in scan1_events:
            self.io.create_event(event)

        subdomains = self.io.get_subdomains()
        assert set(subdomains) == {
            "asdf.blacklanternsecurity.com",
            "blacklanternsecurity.com",
            "www.blacklanternsecurity.com",
        }

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

    async def setup(self, synchronous=False):
        from bbot_server import BBOT_IO

        self.io = BBOT_IO(self.backend, synchronous=synchronous, **self.kwargs)
        if synchronous:
            self.io.setup()
        else:
            await self.io.setup()
        return self.io
