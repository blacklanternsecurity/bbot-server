from tests.test_applets.base import BaseAppletTest


class TestAppletActivity(BaseAppletTest):
    needs_watchdog = True

    async def setup(self):
        # at the beginning, everything should be empty
        assert [a async for a in self.bbot_server.list_activities()] == []

        # create some targets
        await self.bbot_server.create_target(name="evilcorp1", seeds=["www2.evilcorp.com"])
        await self.bbot_server.create_target(name="evilcorp2", seeds=["www.evilcorp.com", "api.evilcorp.com"])

    async def after_scan_1(self):
        # we should have 2 findings
        activities = [a async for a in self.bbot_server.list_activities()]
        assert activities
        for a in activities:
            print(a)
        assert not all(a.host.endswith("evilcorp.com") for a in activities if a.host)

        # query by host
        activities = [a async for a in self.bbot_server.query_activities(domain="evilcorp.com")]
        assert activities
        assert all(a.get("host", "").endswith("evilcorp.com") for a in activities)

    # async def after_scan_2(self):
    #     # advanced findings query
    #     query = {"name": {"$regex": "^CVE-2024-12"}}
    #     findings = [f async for f in self.bbot_server.query_findings(query=query)]
    #     assert len(findings) == 2
    #     assert all(f["name"] == "CVE-2024-12345" for f in findings)

    #     # findings aggregation
    #     aggregate_result = [
    #         f
    #         async for f in self.bbot_server.query_findings(
    #             aggregate=[{"$group": {"_id": "$name", "count": {"$sum": 1}}}, {"$sort": {"_id": 1}}]
    #         )
    #     ]
    #     assert aggregate_result == [{"_id": "CVE-2024-12345", "count": 2}, {"_id": "CVE-2025-54321", "count": 2}]
