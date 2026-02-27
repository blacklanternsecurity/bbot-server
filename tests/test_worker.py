import pytest

import asyncio
from typing import Annotated
from taskiq import Context, TaskiqDepends

from bbot_server import BBOTServer
from bbot.models.pydantic import Event
from bbot_server.worker import BBOTWorker

from .conftest import INGEST_PROCESSING_DELAY


@pytest.mark.asyncio
async def test_worker(bbot_events):
    bbot_server = BBOTServer()
    await bbot_server.setup()
    worker = BBOTWorker(bbot_server)
    await worker.start()

    try:

        @worker.broker.task
        async def insert_event(
            event: Event,
            context: Annotated[Context, TaskiqDepends()],
        ) -> None:
            await context.state.bbot_server.insert_event(event)

        # make sure there aren't any events in the database
        db_events = [e async for e in bbot_server.list_events()]
        assert len(db_events) == 0

        # spawn tasks to insert events
        scan1_events = bbot_events[0]
        for event in scan1_events:
            await insert_event.kiq(event)

        await asyncio.sleep(INGEST_PROCESSING_DELAY)

        db_events = [e async for e in bbot_server.list_events()]
        assert db_events
        assert len(db_events) == len(scan1_events)
    finally:
        await worker.stop()
        await bbot_server.cleanup()
