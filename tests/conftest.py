import os
import sys
import json
import time
import httpx
import pytest  # noqa
import shutil
import signal
import asyncio  # noqa
import logging
import subprocess
import pytest_asyncio
from pathlib import Path
from omegaconf import OmegaConf
from contextlib import suppress

from bbot_server.config import BBOT_SERVER_CONFIG
from .gen_scan_data import *


# how long to wait for new events to be ingested
# this can take a long time on CI because of the tiny instance size
INGEST_PROCESSING_DELAY = 10.0


# set root logger to include date in the format
logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)


log = logging.getLogger(__name__)

PROJ_ROOT = Path(__file__).parent.parent
BBCTL_FILE = PROJ_ROOT / "bbot_server" / "cli" / "bbctl.py"
TEST_CONFIG_PATH = Path(__file__).parent / "test_config.yml"
BBCTL_COMMAND = [sys.executable, str(BBCTL_FILE), "--config", str(TEST_CONFIG_PATH)]

BBOT_SERVER_TEST_DIR = Path("/tmp/.bbot_server_test")
BBOT_SERVER_TEST_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def bbot_server_config():
    # load test file omegaconf config
    test_config = OmegaConf.load(TEST_CONFIG_PATH)
    return OmegaConf.merge(BBOT_SERVER_CONFIG, test_config)


@pytest_asyncio.fixture(params=[{"interface": "python"}, {"interface": "http"}])
# @pytest_asyncio.fixture(params=[{"interface": "http"}])
async def bbot_server(request, mongo_cleanup, redis_cleanup, bbot_server_config):
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
def bbot_watchdog(mongo_cleanup, redis_cleanup):
    command = [*BBCTL_COMMAND, "server", "start", "--watchdog-only"]
    watchdog_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    try:
        # Wait for watchdog to be ready by monitoring stderr
        ready = False
        for _ in range(50):  # 10 second timeout (50 * 0.2)
            line = watchdog_process.stderr.readline()
            log.critical(f"Watchdog: {line.strip()}")
            if "[INFO] Subscribed to bbot:stream:events" in line:
                ready = True
                break

        if not ready:
            raise Exception("Watchdog failed to start and subscribe to events")

        # here, start a thread to tail the watchdog's stderr
        def tail_stderr():
            while watchdog_process.poll() is None:
                line = watchdog_process.stderr.readline()
                if line:
                    log.critical(f"Watchdog: {line.strip()}")

        import threading

        stderr_thread = threading.Thread(target=tail_stderr, daemon=True)
        stderr_thread.start()

        yield watchdog_process

        watchdog_process.send_signal(signal.SIGINT)
    finally:
        try:
            watchdog_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            log.error("Watchdog process timed out, killing forcefully")
            watchdog_process.kill()


@pytest.fixture
def bbot_server_http(mongo_cleanup, redis_cleanup):
    command = [*BBCTL_COMMAND, "server", "start", "--api-only"]

    # Start process in its own process group
    for _ in range(20):
        server_process = subprocess.Popen(command, preexec_fn=os.setsid, stderr=subprocess.PIPE, text=True)
        time.sleep(2)
        if server_process.poll() is None:
            break
        else:
            server_stderr = server_process.stderr.read()
            log.error(f"Failed to start server: return code: {server_process.returncode}")
            log.error(f"Server stderr: {server_stderr}")

    # start thread to tail the server's stderr
    def tail_stderr():
        while server_process.poll() is None:
            line = server_process.stderr.readline()
            if line:
                log.critical(f"Server: {line.strip()}")

    import threading

    stderr_thread = threading.Thread(target=tail_stderr, daemon=True)
    stderr_thread.start()

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
        text=True,
    )

    # Start a thread to tail the agent's stderr
    def tail_stderr():
        while agent_process.poll() is None:
            line = agent_process.stderr.readline()
            if line:
                log.critical(f"Agent: {line.strip()}")
            else:
                time.sleep(0.1)

    import threading

    stderr_thread = threading.Thread(target=tail_stderr, daemon=True)
    stderr_thread.start()

    # give agent a few seconds to start
    time.sleep(INGEST_PROCESSING_DELAY)
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
            log.info(f"Agent process output - stdout: {stdout.decode()}, stderr: {stderr.decode()}")
        if agent_process.poll() is None:
            log.error("Agent process still running, killing forcefully")
            agent_process.kill()


@pytest_asyncio.fixture
async def mongo_cleanup():
    """
    Clear the mongo database before and after each test
    """
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(BBOT_SERVER_CONFIG["event_store"]["uri"])

    async def clear_everything():
        await client.drop_database("test_bbot_server_events")
        await client.drop_database("test_bbot_server_assets")
        await client.drop_database("test_bbot_server_userdata")

    await clear_everything()
    yield
    await clear_everything()


@pytest_asyncio.fixture
async def redis_cleanup(bbot_server_config):
    """
    Clear the redis database before and after each test
    """
    import redis.asyncio as redis

    redis_uri = bbot_server_config.get("message_queue", {}).get("uri", "redis://localhost:6379/15")

    # Connect to Redis
    r = redis.from_url(redis_uri)

    # Clear before test
    await r.flushdb()

    yield

    # Clear after test
    await r.flushdb()

    # Close connection
    await r.aclose()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_sessionfinish(session, exitstatus):
    # Wipe out testing home dir
    shutil.rmtree(BBOT_SERVER_TEST_DIR, ignore_errors=True)
    yield
