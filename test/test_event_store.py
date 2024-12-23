import pytest

from bbot_server.event_store import BACKEND_CHOICES, EventStore


@pytest.mark.asyncio
async def test_event_store(bbot_events):
    assert len(bbot_events) == 20

    assert BACKEND_CHOICES == ["mongo"]
    uris = {"mongo": "mongodb://localhost:27017/test_bbot_events"}

    for backend in BACKEND_CHOICES:
        db_name = uris[backend].split("/")[-1]
        event_store = EventStore(backend, config={"uri": uris[backend]})
        await event_store.setup()
        # clear the event store
        await event_store.clear(confirm=f"WIPE {db_name}")
        # make sure it's empty
        assert [e async for e in event_store.get_events()] == []
        # insert the events
        await event_store.setup()
        for event in bbot_events:
            await event_store.insert_event(event)

    bbot_mongo_events = [e async for e in event_store.get_events()]
    bbot_mongo_events.sort(key=lambda x: x.timestamp)

    assert bbot_mongo_events == bbot_events
