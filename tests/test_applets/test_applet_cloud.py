import pytest
from tests.test_applets.base import BaseAppletTest

pytestmark = pytest.mark.skip(reason="Module shelved in Postgres migration")


class TestAppletCloud(BaseAppletTest):
    needs_watchdog = True

    async def after_scan_1(self):
        cloudcheck_result = await self.bbot_server.cloudcheck("www.evilcorp.azure.com")
        assert len(cloudcheck_result) >= 1
        providers = [r["provider"] for r in cloudcheck_result]
        assert any("Microsoft" in p for p in providers)
        assert all(r["provider_type"] == "cloud" for r in cloudcheck_result)

        cloud_providers = await self.bbot_server.get_cloud_providers_for_asset("cname.evilcorp.com")
        assert len(cloud_providers) >= 1
        providers_list = [cp["provider"] for cp in cloud_providers]
        assert any("Microsoft" in p for p in providers_list)
        # Check that we have results for the CNAME record
        cname_records = [cp for cp in cloud_providers if cp["rdtype"] == "CNAME"]
        assert len(cname_records) >= 1
        assert any(cp["record"] == "evilcorp.azure.com" for cp in cname_records)

    async def after_scan_2(self):
        cloud_providers = await self.bbot_server.get_cloud_providers_for_asset("cname.evilcorp.com")
        assert len(cloud_providers) >= 1
        providers_list = [cp["provider"] for cp in cloud_providers]
        assert any("Amazon" in p for p in providers_list)
        # Check that we have results for the CNAME record
        cname_records = [cp for cp in cloud_providers if cp["rdtype"] == "CNAME"]
        assert len(cname_records) >= 1
        assert any(cp["record"] == "evilcorp.amazonaws.com" for cp in cname_records)

        # stats
        stats = await self.bbot_server.cloud_providers_stats()
        # Check that we have at least one cloud provider in stats
        assert len(stats) > 0
        # Check for Microsoft or Amazon providers
        has_microsoft = any("Microsoft" in k for k in stats.keys())
        has_amazon = any("Amazon" in k for k in stats.keys())
        assert has_microsoft or has_amazon

        domain_stats = await self.bbot_server.cloud_providers_stats(domain="evilcorp.com")
        assert any("Amazon" in k for k in domain_stats.keys())

        activities = [a async for a in self.bbot_server.list_activities(type="CLOUD_PROVIDER_CHANGE")]
        assert len(activities) >= 2  # At least 2 cloud provider changes

        # Check that we have activities for the hosts we expect
        activity_hosts = [a.host for a in activities]
        assert "cname.evilcorp.com" in activity_hosts
        assert "evilcorp.azure.com" in activity_hosts or "evilcorp.amazonaws.com" in activity_hosts

        # Check that at least one activity mentions Amazon
        assert any("Amazon" in a.description for a in activities)
