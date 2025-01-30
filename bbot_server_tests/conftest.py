import signal
import asyncio  # noqa
import logging
import pytest
import pytest_asyncio
from contextlib import suppress

from bbot import Scanner
from bbot.models.pydantic import Event
from bbot.modules.base import BaseModule


log = logging.getLogger(__name__)


def get_bbot_server_config():
    from bbot_server.config import BBOT_SERVER_CONFIG

    BBOT_SERVER_CONFIG["event_store"]["uri"] = "mongodb://localhost:27017/test_bbot_server_events"
    BBOT_SERVER_CONFIG["asset_store"]["uri"] = "mongodb://localhost:27017/test_bbot_server_assets"
    return BBOT_SERVER_CONFIG


BBOT_SERVER_CONFIG = get_bbot_server_config()


# def start_server():
#     print("STARTING SERVER")
#     import uvicorn

#     get_bbot_server_config()
#     from bbot_server.api import server_app

#     uvicorn.run(server_app, host="localhost", port=8807, log_level="info")


# @pytest.fixture()
# def bbot_server_http():
#     import time
#     import httpx
#     import multiprocessing

#     server_process = multiprocessing.Process(target=start_server)
#     server_process.start()

#     # Wait for the server to be ready
#     while True:
#         try:
#             print("REQUESTING")
#             response = httpx.get("http://localhost:8807/v1/assets/")
#             print("RESPONSE", response, response.json())
#             if response.status_code == 200:
#                 break
#         except httpx.RequestError:
#             print("waiting for server to come up")
#             time.sleep(0.1)

#     yield
#     print("TERMINATING SERVER")
#     server_process.terminate(signal.SIGKILL)
#     server_process.join()


@pytest_asyncio.fixture(scope="function")
async def bbot_server_http():
    import httpx
    import uvicorn
    from uvicorn.server import logger
    from bbot_server.api import make_server_app

    server_app = make_server_app()

    server = uvicorn.Server(uvicorn.Config(server_app, host="127.0.0.1", port=8807, log_level="debug"))
    api = asyncio.create_task(server.serve())

    # Wait for the server to be ready asynchronously
    async with httpx.AsyncClient() as client:
        url = "http://localhost:8807/v1/assets/"
        while True:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    break
            except httpx.RequestError as e:
                logger.error(f"Error connecting to bbot-server: {e}")
                await asyncio.sleep(0.2)

    yield "http://127.0.0.1:8807"

    # server.should_exit = True
    server.force_exit = True
    await server.shutdown()
    await asyncio.sleep(1)
    api.cancel()
    with suppress(BaseException):
        await api


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
    yield
    await client.drop_database("test_bbot_server_events")
    await client.drop_database("test_bbot_server_assets")


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
        scan = Scanner(*cls.targets, config=cls.config)
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
    targets = ["evilcorp.com"]
    dns = {
        "evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
            "AAAA": ["1.2.3.4", "5.6.7.8"],
            "CNAME": ["www.evilcorp.com"],
            "MX": ["10 mail.evilcorp.com"],
            "NS": ["ns1.evilcorp.com", "ns2.evilcorp.com"],
            "SOA": ["ns1.evilcorp.com"],
        },
        "www.evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
        },
        "mail.evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
        },
        "ns1.evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
        },
        "ns2.evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
        },
    }

    class DummyModule(BaseModule):
        watched_events = ["OPEN_TCP_PORT"]

        async def handle_event(self, event):
            if str(event.host) == "www.evilcorp.com":
                if event.type == "OPEN_TCP_PORT" and event.port == 443:
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
    targets = ["evilcorp.com"]
    dns = {
        "evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
            "AAAA": ["1.2.3.4", "5.6.7.8"],
            "CNAME": ["www.evilcorp.com"],
            "MX": ["10 mail2.evilcorp.com"],
            "NS": ["ns1.evilcorp.com", "ns2.evilcorp.com"],
            "SOA": ["ns1.evilcorp.com"],
        },
        "www.evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
        },
        "mail2.evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
        },
        "ns1.evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
        },
        "ns2.evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
        },
    }

    class DummyModule(BaseModule):
        watched_events = ["OPEN_TCP_PORT"]

        async def handle_event(self, event):
            if str(event.host) == "mail2.evilcorp.com":
                if event.type == "OPEN_TCP_PORT" and event.port == 80:
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
        scan2_events = await DummyScan2.run()
        BBOT_EVENTS = scan1_events, scan2_events
    return BBOT_EVENTS


# class AppletTest:
#     def __init__(self, **kwargs):
#         for key, value in kwargs.items():
#             setattr(self, key, value)


# @pytest.fixture
# def applet_test_instance(bbot_server, bbot_events):
#     return AppletTest(
#         bbot_server=bbot_server,
#         scan1_events=bbot_events[0],
#         scan2_events=bbot_events[1],
#     )
