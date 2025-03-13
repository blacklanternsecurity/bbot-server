import os
import time
import httpx
import signal
import asyncio  # noqa
import logging
import pytest  # noqa
import pytest_asyncio
from omegaconf import OmegaConf
from contextlib import suppress
from datetime import datetime, timedelta, timezone
import multiprocessing

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


class BBOTHTTPTestServer:
    def __init__(self, config):
        self.config = config
        self.server_process = None

    def _run_bbot_server(self):
        """Run the BBOT server in a separate process."""
        import uvicorn
        from uvicorn.config import Config
        from bbot_server.api import make_server_app

        server_app = make_server_app(config=self.config)
        server = uvicorn.Server(Config(server_app, host="127.0.0.1", port=8807, log_level="info"))
        server.run()

    def start(self):
        print("STARTING SERVER")
        self.server_process = multiprocessing.Process(target=self._run_bbot_server, daemon=True)
        self.server_process.start()

        # Wait for the server to be ready
        url = "http://127.0.0.1:8807/v1/assets/"
        max_retries = 30
        retry_count = 0

        while retry_count < max_retries:
            try:
                response = httpx.get(url)
                if response.status_code == 200:
                    break
            except httpx.RequestError:
                pass

            time.sleep(0.2)
            retry_count += 1

        if retry_count >= max_retries:
            self.stop()  # Use our stop method instead of direct terminate
            raise RuntimeError("Failed to start bbot-server")

    def stop(self):
        if self.server_process and self.server_process.is_alive():
            try:
                self.server_process.terminate()
                self.server_process.join(timeout=0.5)

                # If still alive after terminate and join, force kill
                if self.server_process.is_alive():
                    log.debug("Killing server process because it didn't die properly the first time")
                    os.kill(self.server_process.pid, signal.SIGKILL)
                    self.server_process.join(timeout=1)
            except Exception as e:
                log.warning(f"Error stopping server process: {e}")

            # Explicitly set to None to help garbage collection
            self.server_process = None


@pytest_asyncio.fixture
def bbot_server_http(bbot_server_config, mongo_cleanup):
    bbot_server_http = BBOTHTTPTestServer(bbot_server_config)
    bbot_server_http.start()
    yield bbot_server_http
    bbot_server_http.stop()


@pytest_asyncio.fixture(params=[{"interface": "python"}, {"interface": "http"}])
# @pytest_asyncio.fixture
async def bbot_server(request, mongo_cleanup, bbot_server_config):
    from bbot_server import BBOTServer
    from bbot_server.agent import BBOTAgent
    from bbot_server.watchdog import BBOTWatchdog

    watchdog = None
    agent = None
    bbot_server = None
    bbot_server_http = None

    async def _make_bbot_server(config_overrides=None, needs_agent=False, needs_server=False, **kwargs):
        nonlocal watchdog, agent, bbot_server, bbot_server_http, bbot_server_config

        if config_overrides is not None:
            bbot_server_config = OmegaConf.merge(bbot_server_config, config_overrides)

        interface_kwargs = dict(request.param)
        # kwargs = {}
        interface_kwargs.update({"config": bbot_server_config})
        kwargs.update(interface_kwargs)

        # main bbot server
        log.info(f"Instantiating bbot server with kwargs: {kwargs}")
        bbot_server = BBOTServer(**kwargs)
        await bbot_server.setup()

        # clear the message queue
        await bbot_server.message_queue.clear()

        # http server
        if needs_server or kwargs["interface"] == "http":
            bbot_server_http = BBOTHTTPTestServer(bbot_server_config)
            bbot_server_http.start()

        # watchdog
        watchdog = BBOTWatchdog(bbot_server)
        await watchdog.start()

        # agent
        if needs_agent:
            agent = await bbot_server.create_agent(name="test_agent", description="test agent")
            agent = BBOTAgent(name=agent.name, id=agent.id)
            await agent.start()

        return bbot_server, watchdog, agent

    yield _make_bbot_server

    with suppress(Exception):
        await watchdog.stop()
    with suppress(Exception):
        await agent.stop()
    with suppress(Exception):
        await bbot_server.cleanup()
    with suppress(AttributeError):
        bbot_server_http.stop()


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
