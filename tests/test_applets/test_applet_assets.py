from tests.test_applets.base import BaseAppletTest


class TestAppletAssets(BaseAppletTest):
    async def setup(self):
        assert await self.bbot_server.get_hosts() == []

    async def after_scan_1(self):
        assert await self.bbot_server.get_hosts() == ["www.evilcorp.com"]

    async def after_scan_2(self):
        assert await self.bbot_server.get_hosts() == ["mail2.evilcorp.com", "www.evilcorp.com"]

    async def after_archive(self):
        assert await self.bbot_server.get_hosts() == ["mail2.evilcorp.com", "www.evilcorp.com"]
