from tests.test_applets.base import BaseAppletTest
from bbot_server.modules.targets.targets_models import CreateTarget


class TestAppletActivity(BaseAppletTest):
    needs_watchdog = True

    async def setup(self):
        # at the beginning, everything should be empty
        assert [a async for a in self.bbot_server.list_activities()] == []

        # create some targets
        target1 = CreateTarget(name="evilcorp1", target=["tech.evilcorp.com"])
        target2 = CreateTarget(name="evilcorp2", target=["evilcorp.com"], blacklist=["api.evilcorp.com"])
        self.target1 = await self.bbot_server.create_target(target1)
        self.target2 = await self.bbot_server.create_target(target2)

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

        activities = [a async for a in self.bbot_server.query_activities(domain="tech.evilcorp.com")]
        sorted_descriptions = sorted(a["description"] for a in activities)
        assert sorted_descriptions == [
            "Host t1.tech.evilcorp.com became in-scope for target evilcorp1 due to in-scope host SELF->t1.tech.evilcorp.com",
            "Host t1.tech.evilcorp.com became in-scope for target evilcorp2 due to in-scope host SELF->t1.tech.evilcorp.com",
            "Host t2.tech.evilcorp.com became in-scope for target evilcorp1 due to in-scope host SELF->t2.tech.evilcorp.com",
            "Host t2.tech.evilcorp.com became in-scope for target evilcorp2 due to in-scope host SELF->t2.tech.evilcorp.com",
            "New DNS link: t1.tech.evilcorp.com -(A)-> [192.168.1.1]",
            "New DNS link: t2.tech.evilcorp.com -(A)-> [192.168.1.2]",
            "New asset: [t1.tech.evilcorp.com]",
            "New asset: [t2.tech.evilcorp.com]",
            "New open port: [t1.tech.evilcorp.com:443]",
            "New open port: [t1.tech.evilcorp.com:80]",
            "New open port: [t2.tech.evilcorp.com:443]",
            "New technology discovered on t1.tech.evilcorp.com: [cpe:/a:apache:http_server:2.4.12]",
            "New technology discovered on t2.tech.evilcorp.com: [cpe:/a:apache:http_server:2.4.12]",
            "New technology discovered on t2.tech.evilcorp.com: [cpe:/a:microsoft:internet_information_services]",
        ]

        # activities aggregation
        aggregate_result = [
            a
            async for a in self.bbot_server.query_activities(
                domain="tech.evilcorp.com",
                aggregate=[{"$group": {"_id": "$host", "count": {"$sum": 1}}}, {"$sort": {"_id": 1}}],
            )
        ]
        assert aggregate_result == [
            {"_id": "t1.tech.evilcorp.com", "count": 7},
            {"_id": "t2.tech.evilcorp.com", "count": 7},
        ]

        # test count
        count = await self.bbot_server.count_activities(domain="tech.evilcorp.com")
        assert count == 14

        # NOTE: we do not allow filtering activities by target ID.
        # Why? Because activities can grow to a much larger size than assets, and maintaining up-to-date target IDs on them can become too expensive.
        # If you want to filter activities by target ID, get the asset hosts you need, then query activities for those hosts.
        # activities = [a async for a in self.bbot_server.query_activities(target_id=self.target1.id)]
        # assert activities
        # assert all(self.target1.id in a.scope for a in activities)
