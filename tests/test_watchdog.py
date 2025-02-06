import pytest

import asyncio
from typing import Annotated
from taskiq import Context, TaskiqDepends

from bbot.models.pydantic import Event


@pytest.mark.asyncio
async def test_watchdog(bbot_events):
    from bbot_server import BBOTServer
    from bbot_server.watchdog.worker import WatchdogWorker

    bbot_server = BBOTServer()
    watchdog = WatchdogWorker(bbot_server)
    await watchdog.setup()

    @watchdog.broker.task
    async def insert_event(
        event: Event,
        context: Annotated[Context, TaskiqDepends()],
    ) -> None:
        print(f"INSERTING EVENT: {event}")
        await context.state.bbot_server.insert_event(event)

    # make sure there aren't any events in the database
    db_events = await bbot_server.get_events()
    assert len(db_events) == 0

    # spawn tasks to insert events
    scan1_events = bbot_events[0]
    for event in scan1_events:
        await insert_event.kiq(event)

    await asyncio.sleep(5)

    db_events = await bbot_server.get_events()
    assert db_events
    assert len(db_events) == len(scan1_events)

    await watchdog.cleanup()
