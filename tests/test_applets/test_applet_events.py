from ..conftest import *

from tests.test_applets.base import BaseAppletTest


@pytest.mark.asyncio
async def test_events_websocket_ingest(bbot_server, bbot_events):
    scan1_events, scan2_events = bbot_events

    bbot_server = await bbot_server()

    # list all events
    events = [e async for e in bbot_server.list_events()]
    assert events == []

    # insert events via websocket
    async def event_generator():
        for event in scan1_events:
            yield event

    agen = event_generator()
    await bbot_server.consume_event_stream(agen)
    await asyncio.sleep(INGEST_PROCESSING_DELAY)

    # pull them out and compare them to the original events
    events = [e async for e in bbot_server.list_events()]
    events.sort(key=lambda x: x.timestamp)
    assert events == scan1_events


@pytest.mark.asyncio
async def test_events_http_ingest(bbot_server, bbot_events):
    scan1_events, scan2_events = bbot_events

    bbot_server = await bbot_server()

    events = [e async for e in bbot_server.list_events()]
    assert events == []

    # insert events via http
    for event in scan1_events:
        await bbot_server.insert_event(event)
    await asyncio.sleep(INGEST_PROCESSING_DELAY)

    events = [e async for e in bbot_server.list_events()]
    events.sort(key=lambda x: x.timestamp)
    assert events == scan1_events


class TestAppletEvents(BaseAppletTest):
    needs_worker = True

    async def setup(self):
        route = self.bbot_server.route_maps["tail_events"]
        assert route.fastapi_route.path == "/events/tail"
        # assert route.endpoint_type == "websocket"

    async def after_scan_1(self):
        events = [e async for e in self.bbot_server.list_events()]
        # TODO: why does this change sometimes?
        assert 30 <= len(events) <= 40
        assert len(self.event_messages) == len(events)

    async def after_scan_2(self):
        events = [e async for e in self.bbot_server.list_events()]
        assert 60 <= len(events) <= 80
        assert len(self.event_messages) == len(events)

        # filter events by type
        dns_events = [e async for e in self.bbot_server.list_events(type="DNS_NAME")]
        assert all(e.type == "DNS_NAME" for e in dns_events)
        assert len(dns_events) == 22

        # filter events by host
        host_events = [e async for e in self.bbot_server.list_events(host="t2.tech.evilcorp.com")]
        assert all(e.host == "t2.tech.evilcorp.com" for e in host_events)
        event_types = {}
        for event in host_events:
            event_types[event.type] = event_types.get(event.type, 0) + 1
        assert event_types == {"DNS_NAME": 2, "OPEN_TCP_PORT": 2, "TECHNOLOGY": 2}

        host_events = [e async for e in self.bbot_server.list_events(host="evilcorp.com")]
        assert all(e.host == "evilcorp.com" for e in host_events)
        assert len(host_events) == 4
        modules = {}
        for event in host_events:
            modules[event.module] = modules.get(event.module, 0) + 1
        assert modules == {"SEED": 2, "speculate": 2}

        host_events = [e async for e in self.bbot_server.list_events(host="com")]
        assert host_events == []

        # filter events by domain
        domain_events = [e async for e in self.bbot_server.list_events(domain="com")]
        assert domain_events
        assert all(e.host.endswith(".com") for e in domain_events)

        domain_events = [e async for e in self.bbot_server.list_events(domain="evilcorp.com")]
        assert domain_events
        assert all(e.host.endswith(".evilcorp.com") or e.host == "evilcorp.com" for e in domain_events)

        domain_events = [e async for e in self.bbot_server.list_events(domain="tech.evilcorp.com")]
        assert domain_events
        assert all(e.host.endswith(".tech.evilcorp.com") or e.host == "tech.evilcorp.com" for e in domain_events)

        domain_events = [e async for e in self.bbot_server.list_events(domain="t1.tech.evilcorp.com")]
        assert domain_events
        assert all(e.host.endswith(".t1.tech.evilcorp.com") or e.host == "t1.tech.evilcorp.com" for e in domain_events)

        domain_events = [e async for e in self.bbot_server.list_events(domain="asdf.t1.tech.evilcorp.com")]
        assert domain_events == []

        # advanced querying
        events = [
            e
            async for e in self.bbot_server.query_events(
                query={"data_json.technology": {"$regex": "apache"}}, domain="tech.evilcorp.com"
            )
        ]
        assert events
        assert all(
            e["host"].endswith(".tech.evilcorp.com") and "apache" in e["data_json"]["technology"] for e in events
        )

        # test count
        count = await self.bbot_server.count_events(domain="tech.evilcorp.com")
        assert count == 12
