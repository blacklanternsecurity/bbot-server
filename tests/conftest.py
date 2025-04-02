import os
import sys
import json
import time
import httpx
import pytest  # noqa
import signal
import asyncio  # noqa
import logging
import subprocess
import pytest_asyncio
from pathlib import Path
from omegaconf import OmegaConf
from contextlib import suppress
from datetime import datetime, timedelta, timezone

from bbot_server.config import BBOT_SERVER_CONFIG

from bbot import Scanner
from bbot.models.pydantic import Event
from bbot.modules.base import BaseModule


log = logging.getLogger(__name__)

PROJ_ROOT = Path(__file__).parent.parent
BBCTL_FILE = PROJ_ROOT / "bbot_server" / "cli" / "bbctl.py"
TEST_CONFIG_PATH = Path(__file__).parent / "test_config.yml"
BBCTL_COMMAND = [sys.executable, str(BBCTL_FILE), "--config", str(TEST_CONFIG_PATH)]


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


@pytest_asyncio.fixture(params=[{"interface": "python"}, {"interface": "http"}])
# @pytest_asyncio.fixture
async def bbot_server(request, mongo_cleanup, bbot_server_config):
    from bbot_server import BBOTServer
    from bbot_server.message_queue import MessageQueue

    bbot_server = None
    message_queue = None
    # underlying_bbot_server = None

    async def _make_bbot_server(
        config_overrides=None, needs_agent=False, needs_api=False, needs_watchdog=True, **kwargs
    ):
        nonlocal bbot_server, bbot_server_config

        if config_overrides is not None:
            bbot_server_config = OmegaConf.merge(bbot_server_config, config_overrides)

        interface_kwargs = dict(request.param)
        interface_kwargs.update({"config": bbot_server_config})
        kwargs.update(interface_kwargs)

        # main bbot server
        log.info(f"Instantiating bbot server with kwargs: {kwargs}")
        bbot_server = BBOTServer(**kwargs)
        await bbot_server.setup()

        # clear message queue
        message_queue = MessageQueue(bbot_server_config)
        await message_queue.setup()
        await message_queue.clear()

        # watchdog
        if needs_watchdog:
            request.getfixturevalue("bbot_watchdog")

        # http server
        if needs_api or kwargs["interface"] == "http":
            request.getfixturevalue("bbot_server_http")

        # agent
        if needs_agent:
            request.getfixturevalue("bbot_agent")

        return bbot_server

    yield _make_bbot_server

    with suppress(Exception):
        await bbot_server.cleanup()
    with suppress(Exception):
        await message_queue.clear()
        await message_queue.cleanup()


@pytest.fixture
def bbot_watchdog():
    command = [*BBCTL_COMMAND, "server", "start", "--watchdog-only"]
    watchdog_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        time.sleep(1)
        yield watchdog_process
        watchdog_process.send_signal(signal.SIGINT)
    finally:
        # Capture stdout/stderr regardless of exit state
        with suppress(Exception):
            stdout, stderr = watchdog_process.communicate(timeout=1)
            log.critical(f"Watchdog process output - stdout: {stdout.decode()}, stderr: {stderr.decode()}")
        try:
            watchdog_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            log.error("Watchdog process timed out, killing forcefully")
            watchdog_process.kill()


@pytest.fixture
def bbot_server_http():
    command = [*BBCTL_COMMAND, "server", "start", "--api-only"]

    # Start process in its own process group
    for _ in range(20):
        server_process = subprocess.Popen(command, preexec_fn=os.setsid)
        time.sleep(2)
        if server_process.poll() is None:
            break
        else:
            log.error(f"Failed to start server: return code: {server_process.returncode}")

    try:
        success = False
        for i in range(1000):
            with suppress(Exception):
                response = httpx.get(f"http://localhost:8807/v1/assets/")
                if getattr(response, "status_code", 0) == 200:
                    success = True
                    break
            time.sleep(0.1)
        if not success:
            raise Exception("Failed to start bbot server")
        time.sleep(0.5)
        yield server_process
        server_process.send_signal(signal.SIGINT)
    finally:
        try:
            server_process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            log.error("Server process timed out, killing process group")
            # Kill the entire process group
            os.killpg(os.getpgid(server_process.pid), signal.SIGKILL)


@pytest.fixture
def bbot_agent(bbot_server_http):
    command = [*BBCTL_COMMAND, "agent", "create", "--name", "test_agent"]
    agent_info = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )
    agent_stdout = agent_info.stdout
    try:
        agent_info = json.loads(agent_stdout)
    except json.JSONDecodeError:
        raise Exception(f"Failed to create agent: (stdout: {agent_stdout}, stderr: {agent_info.stderr})")
    agent_name = agent_info["name"]
    agent_id = agent_info["id"]
    agent_process = subprocess.Popen(
        [*BBCTL_COMMAND, "agent", "start", "--name", agent_name, "--id", agent_id],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # give agent a second to start
    time.sleep(3)
    yield agent_process
    agent_process.send_signal(signal.SIGINT)
    try:
        agent_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    finally:
        # Capture stdout/stderr regardless of exit state
        with suppress(Exception):
            stdout, stderr = agent_process.communicate(timeout=1)
            log.critical(f"Agent process output - stdout: {stdout.decode()}, stderr: {stderr.decode()}")
        if agent_process.poll() is None:
            log.error("Agent process still running, killing forcefully")
            agent_process.kill()


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
