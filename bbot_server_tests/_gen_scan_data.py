import pytest_asyncio

base_dns_mock = {
    "evilcorp.com": {
        "A": ["127.0.0.1"],
        "TXT": ["www.evilcorp.com", "asdf.evilcorp.com", "api.evilcorp.com"],
    },
    "www.evilcorp.com": {
        "A": ["127.0.0.1"],
    },
}

dns_mock_1 = dict(base_dns_mock)
dns_mock_1.update(
    {
        "asdf.evilcorp.com": {
            "A": ["127.0.0.1"],
        }
    }
)

dns_mock_2 = dict(base_dns_mock)
dns_mock_2.update(
    {
        "api.evilcorp.com": {
            "A": ["127.0.0.1"],
        }
    }
)


scan1_events = None
scan2_events = None


async def patch_scan(scan, dns_mock=None):
    # mock DNS
    if dns_mock:
        await scan.helpers.dns._mock_dns(dns_mock)

    # mock port scanning
    from bbot.modules.base import BaseModule

    class DummyPortScanner(BaseModule):
        watched_events = ["IP_ADDRESS", "DNS_NAME"]

        async def handle_event(self, event):
            # port 80 is open on all IPs
            if event.type == "IP_ADDRESS":
                netloc = self.helpers.make_netloc(event.host, 80)
                await self.emit_event(netloc, "OPEN_TCP_PORT", parent=event)
            elif event.type == "DNS_NAME":
                # port 443 is open on all DNS names
                netloc = self.helpers.make_netloc(event.host, 443)
                await self.emit_event(netloc, "OPEN_TCP_PORT", parent=event)

    scan.modules["portscan"] = DummyPortScanner(scan)


@pytest_asyncio.fixture()
async def scan_data():
    from pathlib import Path
    from bbot import Scanner, Preset
    from bbot.models.pydantic import Event

    test_preset_file = Path(__file__).parent / "test_preset.yml"
    test_preset = Preset.from_yaml_file(test_preset_file)

    global scan1_events
    global scan2_events

    if scan1_events is None:
        scan1 = Scanner(preset=test_preset)
        await patch_scan(scan1, dns_mock_1)
        scan1_events = [Event(**e.json()) async for e in scan1.async_start()]

    if scan2_events is None:
        scan2 = Scanner(preset=test_preset)
        await patch_scan(scan2, dns_mock_2)
        scan2_events = [Event(**e.json()) async for e in scan2.async_start()]

    return scan1_events, scan2_events
