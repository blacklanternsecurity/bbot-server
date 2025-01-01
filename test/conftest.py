import pytest
import pytest_asyncio

from bbot import Scanner
from bbot.models.pydantic import Event
from bbot.modules.base import BaseModule


def get_bbot_server_config():
    from bbot_server.config import BBOT_SERVER_CONFIG

    BBOT_SERVER_CONFIG["event_store"]["uri"] = "mongodb://localhost:27017/test_bbot_server_events"
    BBOT_SERVER_CONFIG["asset_store"]["uri"] = "mongodb://localhost:27017/test_bbot_server_assets"
    return BBOT_SERVER_CONFIG


BBOT_SERVER_CONFIG = get_bbot_server_config()


def start_server():
    print("STARTING SERVER")
    import uvicorn

    get_bbot_server_config()
    from bbot_server.api import server_app

    uvicorn.run(server_app, host="localhost", port=8807, log_level="info")


@pytest.fixture()
def bbot_server_http():
    # import time
    # import httpx
    # import multiprocessing

    # server_process = multiprocessing.Process(target=start_server)
    # server_process.start()

    # # Wait for the server to be ready
    # while True:
    #     try:
    #         print("REQUESTING")
    #         response = httpx.get("http://localhost:8807/v1/assets/")
    #         print("RESPONSE", response, response.json())
    #         if response.status_code == 200:
    #             break
    #     except httpx.RequestError:
    #         print("waiting for server to come up")
    #         time.sleep(0.1)

    # yield
    # print("TERMINATING SERVER")
    # server_process.terminate()
    # server_process.join()
    yield


# @pytest_asyncio.fixture(params=[
#     {"interface": "python"},
#     {"interface": "http", "url": "http://localhost:8807/v1"}
# ])
@pytest_asyncio.fixture
async def bbot_server(request, mongo_cleanup, bbot_server_http):
    from bbot_server import BBOTServer

    # bbot_server = BBOTServer(**request.param)
    bbot_server = BBOTServer()
    await bbot_server.setup()
    yield bbot_server
    await bbot_server.cleanup()


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


@pytest_asyncio.fixture
async def bbot_events():
    global BBOT_EVENTS
    if BBOT_EVENTS:
        return BBOT_EVENTS

    bbot_config = {
        "scope": {
            "report_distance": 100,
        }
    }
    bbot_scan = Scanner("evilcorp.com", config=bbot_config)
    mock_data = {
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
    await bbot_scan.helpers.dns._mock_dns(mock_data)
    dummy_module = DummyModule(bbot_scan)
    bbot_scan.modules["dummy_module"] = dummy_module

    bbot_events = []
    async for e in bbot_scan.async_start():
        pydantic_event = Event(**e.json())
        bbot_events.append(pydantic_event)

    bbot_events.sort(key=lambda x: x.timestamp)
    BBOT_EVENTS = bbot_events
    return bbot_events
