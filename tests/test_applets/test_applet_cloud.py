from tests.test_applets.base import BaseAppletTest


class TestAppletCloud(BaseAppletTest):
    needs_watchdog = True

    async def after_scan_1(self):
        assert await self.bbot_server.cloudcheck("www.evilcorp.azure.com") == [
            {"provider": "Azure", "provider_type": "cloud", "belongs_to": "azure.com"}
        ]

        assert await self.bbot_server.get_cloud_providers_for_asset("cname.evilcorp.com") == [
            {
                "belongs_to": "azure.com",
                "provider": "Azure",
                "provider_type": "cloud",
                "rdtype": "CNAME",
                "record": "evilcorp.azure.com",
            }
        ]

    async def after_scan_2(self):
        assert await self.bbot_server.get_cloud_providers_for_asset("cname.evilcorp.com") == [
            {
                "record": "evilcorp.amazonaws.com",
                "belongs_to": "amazonaws.com",
                "provider": "Amazon",
                "provider_type": "cloud",
                "rdtype": "CNAME",
            }
        ]

        # stats
        assert await self.bbot_server.cloud_providers_stats() == {
            "Azure": 1,
            "Amazon": 2,
        }
        assert await self.bbot_server.cloud_providers_stats(domain="evilcorp.com") == {
            "Amazon": 1,
        }

        activities = [a async for a in self.bbot_server.list_activities(type="CLOUD_PROVIDER_CHANGE")]
        assert len(activities) == 4
        activity1, activity2, activity3, activity4 = activities
        assert activity1.host == "cname.evilcorp.com"
        assert activity1.description == "Change in cloud providers on cname.evilcorp.com: Added [Azure]"
        assert activity1.detail["added"] == ["Azure"]
        assert activity1.detail["removed"] == []
        assert activity1.detail["details"] == [
            {
                "record": "evilcorp.azure.com",
                "rdtype": "CNAME",
                "provider": "Azure",
                "provider_type": "cloud",
                "belongs_to": "azure.com",
            }
        ]
        assert activity2.host == "evilcorp.azure.com"
        assert activity2.description == "Change in cloud providers on evilcorp.azure.com: Added [Azure]"
        assert activity2.detail["added"] == ["Azure"]
        assert activity2.detail["removed"] == []
        assert activity2.detail["details"] == [
            {
                "record": "evilcorp.azure.com",
                "rdtype": "SELF",
                "provider": "Azure",
                "provider_type": "cloud",
                "belongs_to": "azure.com",
            }
        ]
        assert activity3.host == "cname.evilcorp.com"
        assert (
            activity3.description == "Change in cloud providers on cname.evilcorp.com: Added [Amazon], Removed [Azure]"
        )
        assert activity3.detail["added"] == ["Amazon"]
        assert activity3.detail["removed"] == ["Azure"]
        assert activity3.detail["details"] == [
            {
                "record": "evilcorp.amazonaws.com",
                "rdtype": "CNAME",
                "provider": "Amazon",
                "provider_type": "cloud",
                "belongs_to": "amazonaws.com",
            }
        ]
        assert activity4.host == "evilcorp.amazonaws.com"
        assert activity4.description == "Change in cloud providers on evilcorp.amazonaws.com: Added [Amazon]"
        assert activity4.detail["added"] == ["Amazon"]
        assert activity4.detail["removed"] == []
        assert activity4.detail["details"] == [
            {
                "record": "evilcorp.amazonaws.com",
                "rdtype": "SELF",
                "provider": "Amazon",
                "provider_type": "cloud",
                "belongs_to": "amazonaws.com",
            }
        ]
