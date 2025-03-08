import asyncio  # noqa
import logging
import pytest  # noqa
import pytest_asyncio
from omegaconf import OmegaConf
from contextlib import suppress
from datetime import datetime, timedelta, timezone

from bbot_server.config import BBOT_SERVER_CONFIG

from bbot import Scanner
from bbot.models.pydantic import Event
from bbot.modules.base import BaseModule

log = logging.getLogger(__name__)


@pytest.fixture
def bbot_server_config():
    config_overrides = {
        "event_store": {
            "uri": "mongodb://localhost:27017/test_bbot_server_events",
        },
        "asset_store": {
            "uri": "mongodb://localhost:27017/test_bbot_server_assets",
        },
        "user_store": {
            "uri": "mongodb://localhost:27017/test_bbot_server_userdata",
        },
    }
    return OmegaConf.merge(BBOT_SERVER_CONFIG, config_overrides)


@pytest_asyncio.fixture(scope="function")
async def bbot_server_http(bbot_server_config, mongo_cleanup):
    import httpx
    import uvicorn
    from uvicorn.server import logger
    from bbot_server.api import make_server_app

    server = None
    api = None

    async def _make_bbot_server_http(config_overrides=None):
        nonlocal server, api, bbot_server_config

        if config_overrides is not None:
            bbot_server_config = OmegaConf.merge(bbot_server_config, config_overrides)

        server_app = make_server_app(config=bbot_server_config)

        server = uvicorn.Server(uvicorn.Config(server_app, host="127.0.0.1", port=8807, log_level="info"))
        api = asyncio.create_task(server.serve())

        # Wait for the server to be ready
        url = "http://127.0.0.1:8807/v1/assets/"
        while True:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        break
            except httpx.RequestError as e:
                logger.debug(f"Error connecting to bbot-server at {url}: {e}")
            await asyncio.sleep(0.2)

    yield _make_bbot_server_http

    # server.should_exit = True
    if server is not None:
        server.force_exit = True
        await server.shutdown()
        await asyncio.sleep(0.5)
    if api is not None:
        api.cancel()
        with suppress(BaseException):
            await api


@pytest_asyncio.fixture(params=[{"interface": "python"}, {"interface": "http"}])
# @pytest_asyncio.fixture
async def bbot_server(request, mongo_cleanup, bbot_server_config, bbot_server_http):
    from bbot_server import BBOTServer
    from bbot_server.agent import BBOTAgent
    from bbot_server.watchdog import BBOTWatchdog

    watchdog = None
    agent = None
    bbot_server = None

    async def _make_bbot_server(config_overrides=None, needs_agent=False):
        nonlocal watchdog, agent, bbot_server, bbot_server_config

        if config_overrides is not None:
            bbot_server_config = OmegaConf.merge(bbot_server_config, config_overrides)

        kwargs = dict(request.param)
        # kwargs = {}
        kwargs.update({"config": bbot_server_config})

        # main bbot server
        bbot_server = BBOTServer(**kwargs)
        await bbot_server.setup()

        # clear the message queue
        await bbot_server.message_queue.clear()

        # http server
        await bbot_server_http(config_overrides=config_overrides)

        # watchdog
        watchdog = BBOTWatchdog(bbot_server)
        await watchdog.start()

        # agent
        if needs_agent:
            agent = await bbot_server.create_agent(name="test_agent", description="test agent")
            agent = BBOTAgent(name=agent.name, id=agent.id)
            await agent.start()

        return bbot_server

    yield _make_bbot_server

    with suppress(Exception):
        await watchdog.stop()
    with suppress(Exception):
        await agent.stop()
    with suppress(Exception):
        await bbot_server.cleanup()


BBOT_EVENTS = []


@pytest_asyncio.fixture
async def mongo_cleanup():
    """
    Clear the mongo database before and after each test
    """
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(BBOT_SERVER_CONFIG["event_store"]["uri"])
    await client.drop_database("test_bbot_server_events")
    await client.drop_database("test_bbot_server_assets")
    await client.drop_database("test_bbot_server_userdata")
    yield
    await client.drop_database("test_bbot_server_events")
    await client.drop_database("test_bbot_server_assets")
    await client.drop_database("test_bbot_server_userdata")


class DummyScan:
    targets = []
    dns = {}
    config = {
        "scope": {
            "report_distance": 100,
        }
    }

    @classmethod
    async def run(cls):
        scan = Scanner(scan_name=cls.name, *cls.targets, config=cls.config)
        await scan.helpers.dns._mock_dns(cls.dns)
        for i, dummy_module in enumerate(cls.dummy_modules):
            dummy_module = dummy_module(scan)
            scan.modules[f"dummy_module_{i}"] = dummy_module
        events = []
        async for e in scan.async_start():
            event = Event(**e.json())
            events.append(event)
        events.sort(key=lambda x: x.timestamp)
        return events


class DummyScan1(DummyScan):
    name = "scan1"
    targets = ["evilcorp.com"]
    dns = {
        "evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
            "TXT": [
                "openport80a.evilcorp.com",
                "openport80b.evilcorp.com",
                "openport443.evilcorp.com",
            ],
        },
        "openport80a.evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
        },
        "openport80b.evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
        },
        "openport443.evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
        },
    }

    class DummyModule(BaseModule):
        watched_events = ["OPEN_TCP_PORT"]

        async def handle_event(self, event):
            if str(event.host) in ("openport80a.evilcorp.com", "openport80b.evilcorp.com"):
                if event.type == "OPEN_TCP_PORT" and event.port == 80:
                    await self.emit_event(
                        {
                            "severity": "HIGH",
                            "description": "That's a paddlin'",
                            "host": event.host,
                            "url": f"https://{event.host}",
                        },
                        "VULNERABILITY",
                        parent=event,
                    )

    dummy_modules = [DummyModule]


class DummyScan2(DummyScan):
    name = "scan2"
    targets = ["evilcorp.com"]
    dns = {
        "evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
            "TXT": [
                "openport80a.evilcorp.com",
                "openport80b.evilcorp.com",
                "openport443.evilcorp.com",
            ],
        },
        "openport80a.evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
        },
        "openport80b.evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
        },
        "openport443.evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
        },
    }

    class DummyModule(BaseModule):
        watched_events = ["OPEN_TCP_PORT"]

        async def handle_event(self, event):
            if event.type == "OPEN_TCP_PORT" and (
                str(event.host) == "openport80b.evilcorp.com"
                and event.port == 80
                or str(event.host) == "openport443.evilcorp.com"
                and event.port == 443
            ):
                await self.emit_event(
                    {
                        "severity": "HIGH",
                        "description": "That's a paddlin'",
                        "host": event.host,
                        "url": f"http://{event.host}",
                    },
                    "VULNERABILITY",
                    parent=event,
                )

    dummy_modules = [DummyModule]


@pytest_asyncio.fixture
async def bbot_events():
    global BBOT_EVENTS
    if not BBOT_EVENTS:
        scan1_events = await DummyScan1.run()
        # scan1 events are 91 days old
        for event in scan1_events:
            event.timestamp = (datetime.now(timezone.utc) - timedelta(days=91)).timestamp()
        scan2_events = await DummyScan2.run()
        # scan2 events are 89 days old
        for event in scan2_events:
            event.timestamp = (datetime.now(timezone.utc) - timedelta(days=89)).timestamp()
        BBOT_EVENTS = scan1_events, scan2_events
    return BBOT_EVENTS
