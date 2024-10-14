import pytest
import logging
from datetime import timedelta

log = logging.getLogger("bbot_server.test.gen_scan_data")

from bbot import Scanner, Preset
from bbot_server.models import Event
from bbot_server.test import helpers

base_preset = Preset.from_dict(
    {
        # "debug": True,
        "target": ["blacklanternsecurity.com"],
        "modules": [
            "httpx",
        ],
        "config": {
            "home": "/tmp/.bbotio_test",
            "omit_event_types": ["RAW_DNS_RECORD", "WEB_PARAMETER"],
            "deps_behavior": "disable",
        },
    }
)


base_assets = {
    "unresolvedtoresolved.blacklanternsecurity.com": {},
    "www.blacklanternsecurity.com": {
        "A": ["127.0.0.1"],
    },
    "newhttpstatus.blacklanternsecurity.com": {
        "A": ["127.0.0.1"],
    },
    "newdnsstatus.blacklanternsecurity.com": {
        "A": ["127.0.0.1"],
    },
    "tagadded.blacklanternsecurity.com": {
        "A": ["127.0.0.1"],
    },
    "tagremoved.blacklanternsecurity.com": {
        "A": ["127.0.0.1"],
    },
    "technologyadded.blacklanternsecurity.com": {
        "A": ["127.0.0.1"],
    },
    "technologyremoved.blacklanternsecurity.com": {
        "A": ["127.0.0.1"],
    },
    "portopened.blacklanternsecurity.com": {
        "A": ["127.0.0.1"],
    },
    "portclosed.blacklanternsecurity.com": {
        "A": ["127.0.0.1"],
    },
    "vulnadded.blacklanternsecurity.com": {
        "A": ["127.0.0.1"],
    },
}

base_dns_mock = {
    "blacklanternsecurity.com": {
        "A": ["127.0.0.1"],
        "TXT": list(base_assets),
    },
}
base_dns_mock.update(base_assets)

dns_mock_1 = dict(base_dns_mock)
dns_mock_1.update(
    {
        "resolvedtounresolved.blacklanternsecurity.com": {
            "A": ["127.0.0.1"],
        },
    }
)
dns_mock_1["www.blacklanternsecurity.com"] = {"TXT": ["resolvedtounresolved.blacklanternsecurity.com"]}

dns_mock_2 = dict(base_dns_mock)
dns_mock_2.update(
    {
        "newdnsstatus.blacklanternsecurity.com": {
            "CNAME": ["unresolvedtoresolved.blacklanternsecurity.com"],
        },
        "unresolvedtoresolved.blacklanternsecurity.com": {
            "A": ["127.0.0.1"],
        },
        "newasset.blacklanternsecurity.com": {
            "A": ["127.0.0.1"],
        },
    }
)
dns_mock_2["www.blacklanternsecurity.com"] = {"TXT": ["newasset.blacklanternsecurity.com"]}


scan1_events = None
scan2_events = None


def patch_httpx(scan, httpx_mock_data):
    old_run_live = scan.helpers.run_live

    async def new_run_live(*command, check=False, text=True, **kwargs):
        if command and isinstance(command[0], list) and command[0][0] == "httpx":
            _input = [l for l in kwargs["input"]]
            for target, (port, body) in httpx_mock_data.items():
                for l in _input:
                    if target in l:
                        for _target in [target, f"https://{target}/"]:
                            yield helpers.make_httpx_response(target=_target, input=l, port=port, body=body)
        else:
            async for _ in old_run_live(*command, check=False, text=True, **kwargs):
                yield _

    scan.helpers.run_live = new_run_live


@pytest.fixture
def gen_scan_data(monkeypatch):
    """
    Generates BBOT scan data for testing.

    These two scans are designed to test the progression of assets over time, as they are added, removed, and updated.

    It creates data that tells a bunch of different stories about assets, such as:
        - new asset detected
        - asset has open ports that change over time
        - asset has technologies that change over time
        - asset becomes unresolved and is retired

    """

    def patch_scan1(scan):
        patch_httpx(
            scan,
            {
                "blacklanternsecurity.com:443": ("443", "http://portopened.blacklanternsecurity.com:8443"),
                "portopened.blacklanternsecurity.com:8443": ("8443", ""),
            },
        )

    def patch_scan2(scan):
        patch_httpx(
            scan,
            {
                "blacklanternsecurity.com:443": ("443", "http://portopened.blacklanternsecurity.com:8080"),
                "portopened.blacklanternsecurity.com:8080": ("8080", ""),
            },
        )

    async def _gen_scan_data():

        global scan1_events
        global scan2_events

        if scan1_events is None:
            scan1 = Scanner("1.2.3.4", preset=base_preset)
            patch_scan1(scan1)
            await scan1.helpers.dns._mock_dns(dns_mock_1)
            scan1_events = [e async for e in scan1.async_start()]

        # send scan1 events back in time by 1 year
        for event in scan1_events:
            event.timestamp -= timedelta(days=365)

        if scan2_events is None:
            scan2 = Scanner("1.2.3.0/24", preset=base_preset)
            patch_scan2(scan2)
            await scan2.helpers.dns._mock_dns(dns_mock_2)
            scan2_events = [e async for e in scan2.async_start()]

        return [Event(**e.json()) for e in scan1_events], [Event(**e.json()) for e in scan2_events]

    return _gen_scan_data
