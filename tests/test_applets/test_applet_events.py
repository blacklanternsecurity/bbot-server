from ..conftest import *

from tests.test_applets.base import BaseAppletTest


@pytest.mark.asyncio
async def test_events_websocket_ingest(bbot_server, bbot_events):
    scan1_events, scan2_events = bbot_events

    bbot_server = await bbot_server()

    events = [e async for e in bbot_server.get_events()]
    assert events == []

    # insert events via websocket
    async def event_generator():
        for event in scan1_events:
            yield event

    agen = event_generator()
    await bbot_server.consume_event_stream(agen)
    await asyncio.sleep(0.5)

    # pull them out and compare them to the original events
    events = [e async for e in bbot_server.get_events()]
    events.sort(key=lambda x: x.timestamp)
    assert events == scan1_events


@pytest.mark.asyncio
async def test_events_http_ingest(bbot_server, bbot_events):
    scan1_events, scan2_events = bbot_events

    bbot_server = await bbot_server()

    events = [e async for e in bbot_server.get_events()]
    assert events == []

    # insert events via http
    for event in scan1_events:
        await bbot_server.insert_event(event)
    await asyncio.sleep(0.5)

    events = [e async for e in bbot_server.get_events()]
    events.sort(key=lambda x: x.timestamp)
    assert events == scan1_events


class TestAppletEvents(BaseAppletTest):
    async def setup(self):
        route = self.bbot_server.route_maps["tail_events"]
        assert route.fastapi_route.path == "/events/tail"
        # assert route.endpoint_type == "websocket"

    async def after_scan_1(self):
        # TODO: why does this change sometimes?
        assert 20 <= len(self.event_messages) <= 21

        # make sure our event store is populated
        # events = await self.bbot_server.get_events()
        # assert len(events) == len(self.event_messages)

    async def after_scan_2(self):
        assert 40 <= len(self.event_messages) <= 42

        # make sure the new events arrived in the event store
        # events = await self.bbot_server.get_events()
        # assert len(events) == len(self.event_messages)
