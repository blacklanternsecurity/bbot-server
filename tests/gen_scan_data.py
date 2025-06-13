import shutil
import pytest_asyncio
from pathlib import Path
from datetime import datetime, timedelta, timezone

from bbot.scanner import Scanner
from bbot.models.pydantic import Event
from bbot.modules.base import BaseModule


"""
We test BBOT server by running two BBOT scans:

1. scan1: 91 days ago
2. scan2: 89 days ago

The scans are similar but different enough to test as many features as possible, across all the applets.

Since archival by default happens every 90 days, the first scan will be archived while the second one will not.

Below is a list of the events and how they change between the two scans.

    Host                        Change                                                  Reason
    ----                        ------                                                  ------
    evilcorp.com
    www.evilcorp.com            Open ports: 80 -> None                                  open_ports
    www2.evilcorp.com           Open ports: 80 -> 80                                    open_ports
    api.evilcorp.com            Open ports: None -> 443                                 open_ports
    cname.evilcorp.com          CNAME: evilcorp.azure.com -> evilcorp.amazonaws.com     cloud
    localhost.evilcorp.com      A record: 127.0.0.1 -> 127.0.0.2                        DNS + scope
    t1.tech.evilcorp.com          Technology: apache -> None                              technologies
    t2.tech.evilcorp.com          Technology: IIS -> apache                               technologies

    evilcorp.azure.com          None
    evilcorp.amazonaws.com      None

"""


class DummyScan:
    targets = []
    dns = {}
    config = {
        "scope": {
            "report_distance": 100,
        }
    }
    output_dir = Path("/tmp/.bbot_server_test")

    @classmethod
    async def run(cls):
        # first, clean up the existing output dir
        shutil.rmtree(cls.output_dir / cls.name, ignore_errors=True)
        scan = Scanner(scan_name=cls.name, output_dir=str(cls.output_dir), *cls.targets, config=cls.config)
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
    subdomains = [
        "www.evilcorp.com",
        "www2.evilcorp.com",
        "api.evilcorp.com",
        "cname.evilcorp.com",
        "localhost.evilcorp.com",
        "t1.tech.evilcorp.com",
        "t2.tech.evilcorp.com",
        "testevilcorp.com",  # this exists as a canary to make sure unwanted domains aren't matched in searches
    ]
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
        "localhost.evilcorp.com": {
            "A": ["127.0.0.1"],
        },
        "cname.evilcorp.com": {
            "CNAME": ["evilcorp.azure.com"],
        },
        "t1.tech.evilcorp.com": {
            "A": ["192.168.1.1"],
        },
        "t2.tech.evilcorp.com": {
            "A": ["192.168.1.2"],
        },
        "evilcorp.azure.com": {
            "A": ["127.0.0.3"],
        },
        "evilcorp.amazonaws.com": {
            "A": ["127.0.0.4"],
        },
        "testevilcorp.com": {
            "AAAA": ["dead::beef"],
        },
    }

    class DummyModule(BaseModule):
        watched_events = ["OPEN_TCP_PORT"]

        async def handle_event(self, event):
            # Open ports + vulns
            if event.type == "OPEN_TCP_PORT":
                if str(event.host) in ("www.evilcorp.com", "www2.evilcorp.com"):
                    if event.port == 80:
                        scheme = "https" if event.port == 443 else "http"
                        await self.emit_event(
                            {
                                "name": "CVE-2024-12345",
                                "severity": "HIGH",
                                "description": "That's a paddlin'",
                                "host": event.host,
                                "url": f"{scheme}://{event.host}",
                            },
                            "VULNERABILITY",
                            parent=event,
                        )

                # Technology
                if str(event.host) == "t1.tech.evilcorp.com":
                    scheme = "https" if event.port == 443 else "http"
                    await self.emit_event(
                        {
                            "url": f"{scheme}://{event.host}",
                            "host": event.host,
                            "technology": "cpe:/a:apache:http_server:2.4.12",
                        },
                        "TECHNOLOGY",
                        parent=event,
                    )
                elif str(event.host) == "t2.tech.evilcorp.com" and event.port == 443:
                    scheme = "https" if event.port == 443 else "http"
                    await self.emit_event(
                        {
                            "url": f"{scheme}://{event.host}",
                            "host": event.host,
                            "technology": "cpe:/a:microsoft:internet_information_services",
                        },
                        "TECHNOLOGY",
                        parent=event,
                    )

    dummy_modules = [DummyModule]


class DummyScan2(DummyScan):
    name = "scan2"
    targets = ["evilcorp.com"]
    subdomains = [
        "www.evilcorp.com",
        "www2.evilcorp.com",
        "api.evilcorp.com",
        "cname.evilcorp.com",
        "localhost.evilcorp.com",
        "t1.tech.evilcorp.com",
        "t2.tech.evilcorp.com",
        "testevilcorp.com",
    ]
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
        "localhost.evilcorp.com": {
            "A": ["127.0.0.2"],
        },
        "cname.evilcorp.com": {
            "CNAME": ["evilcorp.amazonaws.com"],
        },
        "t1.tech.evilcorp.com": {
            "A": ["192.168.1.1"],
        },
        "t2.tech.evilcorp.com": {
            "A": ["192.168.1.2"],
        },
        "evilcorp.azure.com": {
            "A": ["127.0.0.3"],
        },
        "evilcorp.amazonaws.com": {
            "A": ["127.0.0.4"],
        },
        "testevilcorp.com": {
            "AAAA": ["dead::beef"],
        },
    }

    class DummyModule(BaseModule):
        watched_events = ["OPEN_TCP_PORT"]

        async def handle_event(self, event):
            if event.type == "OPEN_TCP_PORT":
                if (
                    str(event.host) == "www2.evilcorp.com"
                    and event.port == 80
                    or str(event.host) == "api.evilcorp.com"
                    and event.port == 443
                ):
                    scheme = "https" if event.port == 443 else "http"
                    await self.emit_event(
                        {
                            "name": "CVE-2025-54321",
                            "severity": "CRITICAL",
                            "description": "That's a whippin'",
                            "host": event.host,
                            "url": f"{scheme}://{event.host}",
                        },
                        "VULNERABILITY",
                        parent=event,
                    )

                # Technology
                if str(event.host) == "t2.tech.evilcorp.com" and event.port == 443:
                    scheme = "https" if event.port == 443 else "http"
                    await self.emit_event(
                        {
                            "url": f"{scheme}://{event.host}",
                            "host": event.host,
                            "technology": "cpe:/a:apache:http_server:2.4.12",
                        },
                        "TECHNOLOGY",
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
