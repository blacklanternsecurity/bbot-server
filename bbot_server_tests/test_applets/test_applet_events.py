from contextlib import suppress

from ..conftest import *


@pytest.mark.asyncio
async def test_applet_events(bbot_server, scan_data):
    route = bbot_server.route_maps["tail_events"]
    assert route.fastapi_route.path == "/events/tail"
    assert route.endpoint_type == "websocket"

    events = []

    async def tail_events():
        agen = bbot_server.tail_events()
        try:
            async for event in agen:
                events.append(event)
        finally:
            with suppress(Exception):
                await agen.aclose()

    loop = asyncio.get_event_loop()
    task = loop.create_task(tail_events())
    await asyncio.sleep(1)

    scan1_events, scan2_events = scan_data
    for event in scan1_events:
        await bbot_server.insert_event(event)
    await asyncio.sleep(1)

    # Cancel the task and wait for it to finish
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

    assert len(events) > 0

    await bbot_server.cleanup()
