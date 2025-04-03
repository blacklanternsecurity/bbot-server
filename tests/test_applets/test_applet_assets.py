from tests.test_applets.base import BaseAppletTest


class TestAppletAssets(BaseAppletTest):
    needs_watchdog = True

    async def setup(self):
        # # make sure all asset fields have annotations
        # for field, field_info in self.bbot_server.assets.model.model_fields.items():
        #     if field_info.annotation is None:
        #         raise ValueError(f"Field '{field}' has no type annotation")
        #     if field_info.default_factory is None:
        #         raise ValueError(f"Field '{field}' has no default factory")

        assert await self.bbot_server.get_hosts() == []

    async def after_scan_1(self):
        assert await self.bbot_server.get_hosts() == ["www.evilcorp.com", "www2.evilcorp.com"]

    async def after_scan_2(self):
        assert await self.bbot_server.get_hosts() == [
            "api.evilcorp.com",
            "www.evilcorp.com",
            "www2.evilcorp.com",
        ]

    async def after_archive(self):
        assert await self.bbot_server.get_hosts() == [
            "api.evilcorp.com",
            "www.evilcorp.com",
            "www2.evilcorp.com",
        ]
