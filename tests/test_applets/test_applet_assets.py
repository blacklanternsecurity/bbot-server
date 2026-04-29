import asyncio
import pytest

from bbot_server.assets import Asset
from bbot_server.errors import BBOTServerValueError
from bbot_server.modules.targets.targets_models import CreateTarget

from tests.test_applets.base import BaseAppletTest
from ..conftest import INGEST_PROCESSING_DELAY


class TestAppletAssets(BaseAppletTest):
    needs_worker = True

    async def setup(self):
        # # make sure all asset fields have annotations
        # for field, field_info in self.bbot_server.assets.model.model_fields.items():
        #     if field_info.annotation is None:
        #         raise ValueError(f"Field '{field}' has no type annotation")
        #     if field_info.default_factory is None:
        #         raise ValueError(f"Field '{field}' has no default factory")

        # hosts should be empty
        assert await self.bbot_server.get_hosts() == []
        # assets should be empty
        assert [a async for a in self.bbot_server.list_assets()] == []
        assert [a async for a in self.bbot_server.query_assets()] == []

    async def after_scan_1(self):
        # since this is our first test, and runners are dog slow, it can take a while for the worker etc. to get ready
        # we loop for a while to give them time to start up
        expected_hosts = {
            "1.2.3.4",
            "127.0.0.1",
            "192.168.1.1",
            "192.168.1.2",
            "5.6.7.8",
            "evilcorp.azure.com",
            "api.evilcorp.com",
            "cname.evilcorp.com",
            "evilcorp.com",
            "localhost.evilcorp.com",
            "www.evilcorp.com",
            "www2.evilcorp.com",
            "t1.tech.evilcorp.com",
            "t2.tech.evilcorp.com",
            "testevilcorp.com",
        }
        for _ in range(120):
            hosts = set(await self.bbot_server.get_hosts())
            if hosts == expected_hosts:
                break
            await asyncio.sleep(0.5)
        else:
            assert hosts == expected_hosts, "Hosts don't match expected hosts"

        hosts = {a.host async for a in self.bbot_server.list_assets()}
        assert hosts == expected_hosts

        assets = [a async for a in self.bbot_server.list_assets()]
        assert len(assets) == len(expected_hosts)
        assert all(isinstance(a, Asset) for a in assets)
        assets = [a async for a in self.bbot_server.query_assets()]
        assert len(assets) == len(expected_hosts)
        assert all(isinstance(a, dict) for a in assets)

    async def after_scan_2(self):
        expected_hosts = {
            "1.2.3.4",
            "127.0.0.1",
            "127.0.0.2",
            "192.168.1.1",
            "192.168.1.2",
            "5.6.7.8",
            "evilcorp.azure.com",
            "api.evilcorp.com",
            "evilcorp.amazonaws.com",
            "cname.evilcorp.com",
            "evilcorp.com",
            "localhost.evilcorp.com",
            "www.evilcorp.com",
            "www2.evilcorp.com",
            "t1.tech.evilcorp.com",
            "t2.tech.evilcorp.com",
            "testevilcorp.com",
        }
        assert set(await self.bbot_server.get_hosts()) == expected_hosts

        assets = [a async for a in self.bbot_server.list_assets()]
        assert len(assets) == len(expected_hosts)
        assert all(isinstance(a, Asset) for a in assets)
        assets = [a async for a in self.bbot_server.query_assets()]
        assert len(assets) == len(expected_hosts)
        assert all(isinstance(a, dict) for a in assets)

        # asset types other than findings
        technologies = [a async for a in self.bbot_server.query_assets(type="Technology")]
        assert technologies
        assert all([a["type"] == "Technology" for a in technologies])

        assets = [
            a
            async for a in self.bbot_server.query_assets(
                active=True,
                archived=False,
                query={"cloud_providers": "Akamai"},
                type="Asset",
            )
        ]
        assert not assets

        # query should override type
        findings = [a async for a in self.bbot_server.query_assets(type="Technology", query={"type": "Finding"})]
        assert findings
        assert all([a["type"] == "Finding" for a in findings])
        # same with host
        assets = [
            a
            async for a in self.bbot_server.query_assets(
                host="t1.tech.evilcorp.com", query={"host": "t2.tech.evilcorp.com"}
            )
        ]
        assert assets
        assert all([a["host"] == "t2.tech.evilcorp.com" for a in assets])
        # same with domain
        assets = [
            a
            async for a in self.bbot_server.query_assets(
                domain="evilcorp.com", query={"reverse_host": {"$regex": "^moc.swanozama"}}
            )
        ]
        assert assets
        assert all([a["host"].endswith("amazonaws.com") for a in assets])

        # test limit feature
        assets = [a async for a in self.bbot_server.query_assets(limit=1)]
        assert len(assets) == 1

        # test aggregation feature
        aggregate_result = [
            a
            async for a in self.bbot_server.query_assets(
                type="Finding",
                aggregate=[{"$group": {"_id": "$name", "count": {"$sum": 1}}}, {"$sort": {"_id": -1}}],
            )
        ]
        assert aggregate_result == [{"_id": "CVE-2025-54321", "count": 2}, {"_id": "CVE-2024-12345", "count": 2}]

        # ensure sanitization is working
        with pytest.raises(BBOTServerValueError, match=r"Unauthorized MongoDB query operator: \$where"):
            [a async for a in self.bbot_server.query_assets(query={"host": {"$where": "js"}})]

        # ensure aggregation sanitization is working
        with pytest.raises(BBOTServerValueError, match=r"Unauthorized MongoDB aggregation operator: \$out"):
            [
                a
                async for a in self.bbot_server.query_assets(
                    aggregate=[
                        {"$group": {"_id": "$name", "count": {"$sum": 1}}},
                        {"$sort": {"count": -1}},
                        {"$out": "assets_test"},
                    ]
                )
            ]

        # test pagination
        assets_page_1 = [a async for a in self.bbot_server.query_assets(limit=10)]
        assert len(assets_page_1) == 10
        assets_page_2 = [a async for a in self.bbot_server.query_assets(limit=10, skip=10)]
        # page 2 should have all the hosts that page 1 doesn't
        assert len(assets_page_2) == len(expected_hosts) - 10
        # there should be no overlap between the two pages
        assert set([a["host"] for a in assets_page_1]) & set([a["host"] for a in assets_page_2]) == set()

        assert set([a["host"] for a in assets_page_1 + assets_page_2]) == expected_hosts

        # test count
        count = await self.bbot_server.count_assets(domain="tech.evilcorp.com")
        assert count == 2

        # make sure host_parts field is present
        tech1 = await self.bbot_server.get_asset(host="t1.tech.evilcorp.com")
        assert tech1.host_parts == ["t1", "tech", "evilcorp", "com"]

        # make sure we can search by host_parts
        query = {"host_parts": {"$regex": "^tec"}}
        assets = [a async for a in self.bbot_server.query_assets(query=query)]
        assert {a["host"] for a in assets} == {"t1.tech.evilcorp.com", "t2.tech.evilcorp.com"}

        # test text search feature
        assets = [a async for a in self.bbot_server.query_assets(search="tec")]
        assert {a["host"] for a in assets} == {"t1.tech.evilcorp.com", "t2.tech.evilcorp.com"}
        assets = [a async for a in self.bbot_server.query_assets(search="evilcor")]
        assert {a["host"] for a in assets} == {
            "api.evilcorp.com",
            "cname.evilcorp.com",
            "evilcorp.amazonaws.com",
            "evilcorp.azure.com",
            "evilcorp.com",
            "localhost.evilcorp.com",
            "t1.tech.evilcorp.com",
            "t2.tech.evilcorp.com",
            "www.evilcorp.com",
            "www2.evilcorp.com",
        }

    async def after_archive(self):
        assert set(await self.bbot_server.get_hosts()) == {
            "1.2.3.4",
            "127.0.0.1",
            "127.0.0.2",
            "192.168.1.1",
            "192.168.1.2",
            "5.6.7.8",
            "evilcorp.azure.com",
            "api.evilcorp.com",
            "evilcorp.amazonaws.com",
            "cname.evilcorp.com",
            "evilcorp.com",
            "localhost.evilcorp.com",
            "www.evilcorp.com",
            "www2.evilcorp.com",
            "t1.tech.evilcorp.com",
            "t2.tech.evilcorp.com",
            "testevilcorp.com",
        }

        assert set(await self.bbot_server.get_hosts(domain="com")) == {
            "api.evilcorp.com",
            "cname.evilcorp.com",
            "evilcorp.amazonaws.com",
            "evilcorp.azure.com",
            "evilcorp.com",
            "localhost.evilcorp.com",
            "t1.tech.evilcorp.com",
            "t2.tech.evilcorp.com",
            "testevilcorp.com",
            "www.evilcorp.com",
            "www2.evilcorp.com",
        }
        assert set(await self.bbot_server.get_hosts(domain="evilcorp.com")) == {
            "evilcorp.com",
            "api.evilcorp.com",
            "cname.evilcorp.com",
            "www.evilcorp.com",
            "www2.evilcorp.com",
            "localhost.evilcorp.com",
            "t1.tech.evilcorp.com",
            "t2.tech.evilcorp.com",
        }
        assert set(await self.bbot_server.get_hosts(domain="tech.evilcorp.com")) == {
            "t1.tech.evilcorp.com",
            "t2.tech.evilcorp.com",
        }
        assert set(await self.bbot_server.get_hosts(domain="t1.tech.evilcorp.com")) == {
            "t1.tech.evilcorp.com",
        }
        assert set(await self.bbot_server.get_hosts(domain="asdf.tech.evilcorp.com")) == set()


# test to make sure you can filter assets by target
async def test_applet_target_filter(bbot_server, bbot_events):
    bbot_server = await bbot_server(needs_worker=True)

    target1 = CreateTarget(
        target=["evilcorp.com", "127.0.0.0/30"],
        blacklist=["localhost.evilcorp.com"],
    )
    target1 = await bbot_server.create_target(target1)

    # ingest BBOT events
    scan1_events, scan2_events = bbot_events
    for e in scan1_events:
        await bbot_server.insert_event(e)

    # wait for events to be processed
    await asyncio.sleep(INGEST_PROCESSING_DELAY)

    all_hosts = {
        "evilcorp.com",
        "1.2.3.4",
        "5.6.7.8",
        "192.168.1.1",
        "192.168.1.2",
        "www2.evilcorp.com",
        "api.evilcorp.com",
        "localhost.evilcorp.com",
        "cname.evilcorp.com",
        "www.evilcorp.com",
        "127.0.0.1",
        "evilcorp.azure.com",
        "testevilcorp.com",
        "t1.tech.evilcorp.com",
        "t2.tech.evilcorp.com",
    }

    all_hosts_target1 = {
        "127.0.0.1",
        "evilcorp.com",
        "www2.evilcorp.com",
        "api.evilcorp.com",
        "cname.evilcorp.com",
        "www.evilcorp.com",
        "evilcorp.azure.com",  # this one resolves to 127.0.0.3 so it matches
        "t1.tech.evilcorp.com",
        "t2.tech.evilcorp.com",
    }

    all_hosts_target2 = {
        "1.2.3.4",
        "evilcorp.com",
        "www.evilcorp.com",
        "api.evilcorp.com",
    }

    # get assets (without target filter)
    assets = [a.host async for a in bbot_server.list_assets()]
    assert set(assets) == all_hosts
    hosts = await bbot_server.get_hosts()
    assert set(hosts) == all_hosts

    # get assets (with default target filter)
    assets = [a.host async for a in bbot_server.list_assets(target_id="DEFAULT")]
    assert set(assets) == all_hosts_target1
    hosts = await bbot_server.get_hosts(target_id="DEFAULT")
    assert set(hosts) == all_hosts_target1

    # get assets (with target filter)
    assets = [a.host async for a in bbot_server.list_assets(target_id=target1.id)]
    assert set(assets) == all_hosts_target1
    hosts = await bbot_server.get_hosts(target_id=target1.id)
    assert set(hosts) == all_hosts_target1

    # new target
    target = CreateTarget(
        target=["1.2.3.0/24"],
        blacklist=["www2.evilcorp.com"],
    )
    target = await bbot_server.create_target(target)

    # wait for events to be tagged with new target
    await asyncio.sleep(1)

    # get assets (with new target filter)
    assets = [a.host async for a in bbot_server.list_assets(target_id=target.id)]
    assert set(assets) == all_hosts_target2
    hosts = await bbot_server.get_hosts(target_id=target.id)
    assert set(hosts) == all_hosts_target2


# test to make sure custom attributes on assets are queryable
async def test_applet_custom_attributes(bbot_server, bbot_events):
    bbot_server = await bbot_server(needs_worker=True)

    # skip testing of the http interface (since insertion isn't supported)
    if not bbot_server.is_native:
        return

    # ingest BBOT events to create some assets
    scan1_events, scan2_events = bbot_events
    for e in scan1_events:
        await bbot_server.insert_event(e)

    # wait for events to be processed
    await asyncio.sleep(INGEST_PROCESSING_DELAY)

    # verify assets exist
    hosts = set(await bbot_server.get_hosts())
    assert "evilcorp.com" in hosts
    assert "www.evilcorp.com" in hosts
    assert "api.evilcorp.com" in hosts

    # manually add custom attributes to some assets via the collection
    collection = bbot_server.assets.collection
    await collection.update_one(
        {"host": "evilcorp.com", "type": "Asset"},
        {"$set": {"custom_tag": "important", "risk_score": 95}},
    )
    await collection.update_one(
        {"host": "www.evilcorp.com", "type": "Asset"},
        {"$set": {"custom_tag": "important", "risk_score": 50}},
    )
    await collection.update_one(
        {"host": "api.evilcorp.com", "type": "Asset"},
        {"$set": {"custom_tag": "low-priority", "risk_score": 10}},
    )

    # query by custom attribute - exact match
    results = [a async for a in bbot_server.query_assets(query={"custom_tag": "important"})]
    assert {a["host"] for a in results} == {"evilcorp.com", "www.evilcorp.com"}

    # query by custom attribute - comparison operator
    results = [a async for a in bbot_server.query_assets(query={"risk_score": {"$gte": 50}})]
    assert {a["host"] for a in results} == {"evilcorp.com", "www.evilcorp.com"}

    # query combining custom attribute with built-in filters
    results = [a async for a in bbot_server.query_assets(query={"custom_tag": "important", "host": "evilcorp.com"})]
    assert len(results) == 1
    assert results[0]["host"] == "evilcorp.com"

    # verify custom fields are returned in query results
    results = [a async for a in bbot_server.query_assets(query={"host": "api.evilcorp.com"})]
    assert len(results) == 1
    assert results[0]["custom_tag"] == "low-priority"
    assert results[0]["risk_score"] == 10

    # query for a custom attribute value that doesn't exist
    results = [a async for a in bbot_server.query_assets(query={"custom_tag": "nonexistent"})]
    assert results == []

    # aggregation on custom attributes
    agg_results = [
        a
        async for a in bbot_server.query_assets(
            aggregate=[
                {"$group": {"_id": "$custom_tag", "avg_risk": {"$avg": "$risk_score"}}},
                {"$sort": {"_id": 1}},
            ],
        )
    ]
    assert len(agg_results) == 3
    assert agg_results[0] == {"_id": None, "avg_risk": None}
    assert agg_results[1] == {"_id": "important", "avg_risk": 72.5}
    assert agg_results[2] == {"_id": "low-priority", "avg_risk": 10.0}

    # count with custom attribute filter
    count = await bbot_server.count_assets(query={"custom_tag": "important"})
    assert count == 2


# Verifies the MongoDB predicates the frontend's isEmpty / isNotEmpty operators emit
# (`$in: [null, []]` and `$nin: [null, []]`) correctly distinguish missing-field, explicit-null,
# empty-list, and populated documents on an array field like `open_ports`.
async def test_applet_assets_empty_query_open_ports(bbot_server, bbot_events):
    bbot_server = await bbot_server(needs_worker=True)

    # skip testing of the http interface (since direct collection mutation isn't supported)
    if not bbot_server.is_native:
        return

    # ingest BBOT events to create some assets
    scan1_events, _scan2_events = bbot_events
    for e in scan1_events:
        await bbot_server.insert_event(e)
    await asyncio.sleep(INGEST_PROCESSING_DELAY)

    # pick four distinct hosts and force each into a different open_ports shape
    host_absent = "evilcorp.com"          # field removed entirely
    host_null = "www.evilcorp.com"        # explicit null
    host_empty = "api.evilcorp.com"       # empty list
    host_populated = "cname.evilcorp.com"  # populated

    collection = bbot_server.assets.collection
    await collection.update_one({"host": host_absent, "type": "Asset"}, {"$unset": {"open_ports": ""}})
    await collection.update_one({"host": host_null, "type": "Asset"}, {"$set": {"open_ports": None}})
    await collection.update_one({"host": host_empty, "type": "Asset"}, {"$set": {"open_ports": []}})
    await collection.update_one({"host": host_populated, "type": "Asset"}, {"$set": {"open_ports": [80]}})

    # sanity: confirm the four documents are in the expected shapes
    docs = {
        d["host"]: d
        async for d in collection.find(
            {"host": {"$in": [host_absent, host_null, host_empty, host_populated]}, "type": "Asset"}
        )
    }
    assert "open_ports" not in docs[host_absent]
    assert docs[host_null]["open_ports"] is None
    assert docs[host_empty]["open_ports"] == []
    assert docs[host_populated]["open_ports"] == [80]

    target_hosts = {host_absent, host_null, host_empty, host_populated}

    # isEmpty contract: $in: [null, []] matches missing-field, explicit-null, and empty-list documents.
    is_empty_results = [
        a
        async for a in bbot_server.query_assets(
            type="Asset",
            query={"host": {"$in": list(target_hosts)}, "open_ports": {"$in": [None, []]}},
        )
    ]
    assert {a["host"] for a in is_empty_results} == {host_absent, host_null, host_empty}

    # isNotEmpty contract: $nin: [null, []] matches only the populated document.
    is_not_empty_results = [
        a
        async for a in bbot_server.query_assets(
            type="Asset",
            query={"host": {"$in": list(target_hosts)}, "open_ports": {"$nin": [None, []]}},
        )
    ]
    assert {a["host"] for a in is_not_empty_results} == {host_populated}
