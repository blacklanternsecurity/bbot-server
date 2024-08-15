import pytest
import logging


log = logging.getLogger("bbot.test.modules")


class IOTestBase:
    log = logging.getLogger("bbot.io")

    from bbot_io.test.applets.events import _test_events
    from bbot_io.test.applets.scans import _test_scans
    from bbot_io.test.applets.targets import _test_targets

    from ._gen_scan_data import gen_scan_data, patch_scan

    class Fixtures:
        def __init__(self, monkeypatch):
            self.monkeypatch = monkeypatch

    @pytest.mark.asyncio
    async def test_module_run(self, monkeypatch):
        self.fixtures = self.Fixtures(monkeypatch)

        self.scan1_events, self.scan2_events = await self.gen_scan_data()

        # instantiate io module
        self.io = await self.setup()
        await self.io.setup()

        # test events
        await self.ensure_empty()
        await self._test_events()

        # test scans
        await self.ensure_empty()
        await self._test_scans()

        # test targets
        await self.ensure_empty()
        await self._test_targets()

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

    async def setup(self):
        pass
