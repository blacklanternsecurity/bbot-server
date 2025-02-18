from tests.test_applets.base import BaseAppletTest


class TestAppletAssets(BaseAppletTest):
    async def setup(self):
        assert await self.bbot_server.get_hosts() == []

    async def after_scan_1(self):
        assert await self.bbot_server.get_hosts() == ["openport80a.evilcorp.com", "openport80b.evilcorp.com"]

    async def after_scan_2(self):
        assert await self.bbot_server.get_hosts() == [
            "openport443.evilcorp.com",
            "openport80a.evilcorp.com",
            "openport80b.evilcorp.com",
        ]

    async def after_archive(self):
        assert await self.bbot_server.get_hosts() == [
            "openport443.evilcorp.com",
            "openport80a.evilcorp.com",
            "openport80b.evilcorp.com",
        ]
