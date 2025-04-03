import pytest_asyncio
from pathlib import Path
from datetime import datetime, timedelta, timezone

from bbot import Scanner
from bbot.models.pydantic import Event
from bbot.modules.base import BaseModule


class DummyScan:
    targets = []
    dns = {}
    config = {
        "scope": {
            "report_distance": 100,
        }
    }
    output_dir = "/tmp/.bbot_server_test"

    @classmethod
    async def run(cls):
        scan = Scanner(scan_name=cls.name, output_dir=cls.output_dir, *cls.targets, config=cls.config)
        await scan.helpers.dns._mock_dns(cls.dns)
        for i, dummy_module in enumerate(cls.dummy_modules):
            dummy_module = dummy_module(scan)
            scan.modules[f"dummy_module_{i}"] = dummy_module
        events = []
        async for e in scan.async_start():
            event = Event(**e.json())
            events.append(event)
        events.sort(key=lambda x: x.timestamp)

        out_file = scan.home / "output.json"
        return events, out_file.read_text()


class DummyScan1(DummyScan):
    name = "scan1"
    targets = ["evilcorp.com"]
    subdomains = ["www.evilcorp.com", "www2.evilcorp.com", "api.evilcorp.com"]
    dns = {
        "evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
            "TXT": subdomains,
        },
        "www.evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
        },
        "www2.evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
        },
        "api.evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
        },
    }

    class DummyModule(BaseModule):
        watched_events = ["OPEN_TCP_PORT"]

        async def handle_event(self, event):
            if str(event.host) in ("www.evilcorp.com", "www2.evilcorp.com"):
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
    subdomains = ["www.evilcorp.com", "www2.evilcorp.com", "api.evilcorp.com"]
    dns = {
        "evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
            "TXT": subdomains,
        },
        "www.evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
        },
        "www2.evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
        },
        "api.evilcorp.com": {
            "A": ["1.2.3.4", "5.6.7.8"],
        },
    }

    class DummyModule(BaseModule):
        watched_events = ["OPEN_TCP_PORT"]

        async def handle_event(self, event):
            if event.type == "OPEN_TCP_PORT" and (
                str(event.host) == "www2.evilcorp.com"
                and event.port == 80
                or str(event.host) == "api.evilcorp.com"
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


async def create_dummy_data():
    scan1_events, scan1_out_file = await DummyScan1.run()
    # scan1 events are 91 days old
    for event in scan1_events:
        event.timestamp = (datetime.now(timezone.utc) - timedelta(days=91)).timestamp()
    scan2_events, scan2_out_file = await DummyScan2.run()
    # scan2 events are 89 days old
    for event in scan2_events:
        event.timestamp = (datetime.now(timezone.utc) - timedelta(days=89)).timestamp()
    return (scan1_events, scan2_events), (scan1_out_file, scan2_out_file)


BBOT_DUMMY_DATA = []


@pytest_asyncio.fixture
async def bbot_events():
    global BBOT_DUMMY_DATA
    if not BBOT_DUMMY_DATA:
        BBOT_DUMMY_DATA = await create_dummy_data()
    return BBOT_DUMMY_DATA[0]


@pytest_asyncio.fixture
async def bbot_out_file():
    global BBOT_DUMMY_DATA
    if not BBOT_DUMMY_DATA:
        BBOT_DUMMY_DATA = await create_dummy_data()
    return BBOT_DUMMY_DATA[1]
