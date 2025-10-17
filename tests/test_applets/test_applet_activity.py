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
        activities = [a async for a in self.bbot_server.list_activities()]
        assert activities

        activities = [a async for a in self.bbot_server.query_activities(domain="evilcorp.com")]
        assert activities
        assert all(a.get("host", "").endswith("evilcorp.com") for a in activities)

    async def after_scan_2(self):
        # listing
        activities = [a async for a in self.bbot_server.list_activities()]
        assert activities
        assert not all(a.host.endswith("evilcorp.com") for a in activities if a.host)

        # querying
        activities = [a async for a in self.bbot_server.query_activities(domain="evilcorp.amazonaws.com")]
        assert activities
        assert all(a.get("host", "").endswith("evilcorp.amazonaws.com") for a in activities)

        # activities aggregation
        aggregate_result = [
            a
            async for a in self.bbot_server.query_activities(
                domain="tech.evilcorp.com",
                aggregate=[{"$group": {"_id": "$host", "count": {"$sum": 1}}}, {"$sort": {"_id": 1}}],
            )
        ]
        assert aggregate_result == [
            {"_id": "t1.tech.evilcorp.com", "count": 5},
            {"_id": "t2.tech.evilcorp.com", "count": 5},
        ]
