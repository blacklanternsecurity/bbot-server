import pytest

import asyncio
from typing import Annotated

import httpx
import json
from time import time
from taskiq import Context, TaskiqDepends

from bbot_server import BBOTServer
from bbot.models.pydantic import Event
from bbot_server.watchdog import BBOTWatchdog

from .conftest import INGEST_PROCESSING_DELAY


@pytest.mark.asyncio
async def test_watchdog(bbot_events):
    bbot_server = BBOTServer()
    await bbot_server.setup()
    watchdog = BBOTWatchdog(bbot_server)
    await watchdog.start()

    try:

        @watchdog.broker.task
        async def insert_event(
            event: Event,
            context: Annotated[Context, TaskiqDepends()],
        ) -> None:
            await context.state.bbot_server.insert_event(event)

        # make sure there aren't any events in the database
        db_events = [e async for e in bbot_server.get_events()]
        assert len(db_events) == 0

        # spawn tasks to insert events
        scan1_events = bbot_events[0]
        for event in scan1_events:
            await insert_event.kiq(event)

        await asyncio.sleep(INGEST_PROCESSING_DELAY)

        db_events = [e async for e in bbot_server.get_events()]
        assert db_events
        assert len(db_events) == len(scan1_events)
    finally:
        await watchdog.stop()
        await bbot_server.cleanup()


@pytest.mark.asyncio
async def test_watchdog_webhook_alerts():
    webhook_calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        webhook_calls.append(json.loads(request.content))
        return httpx.Response(204)

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)

    class DummyServer:
        def __init__(self):
            self.config = {"watchdog": {"alerts": {"enabled": True, "webhook_url": "https://example.com/webhook"}}}

        def all_child_applets(self, include_self=True):
            return []

    watchdog = BBOTWatchdog(DummyServer(), http_client=http_client)

    async def fake_get_or_create_asset(*_, **__):
        return None, []

    watchdog._get_or_create_asset = fake_get_or_create_asset  # type: ignore[assignment]

    try:
        event = Event(
            uuid="00000000-0000-0000-0000-000000000001",
            id="ev1",
            type="DNS_NAME",
            scope_description="test scope",
            scan="scan1",
            timestamp=time(),
            parent="root",
            parent_uuid="00000000-0000-0000-0000-000000000000",
            host="example.com",
            data="example.com",
        )

        await watchdog._event_listener(event.model_dump())
        assert webhook_calls
        payload = webhook_calls[0]
        assert payload["summary"].startswith("New event detected")
        assert payload["event"]["type"]
        assert watchdog._last_alert_client_verify is False
    finally:
        await http_client.aclose()
