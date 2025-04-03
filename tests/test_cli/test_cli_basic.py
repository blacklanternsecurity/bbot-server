# tests for basic CLI functionality like debugging, etc.

import sys
import yaml
import subprocess
from pathlib import Path
from bbot_server.cli.bbctl import main

from tests.conftest import BBCTL_COMMAND


# make sure error handling works properly
def test_cli_debugging():
    bogus_server_url = "http://localhost:58777"
    error_message = f"[ERROR] Error making GET request -> {bogus_server_url}/events/?archived=False&active=True: All connection attempts failed\n"

    # induce an error with a bogus server URL
    command = BBCTL_COMMAND + ["-u", bogus_server_url, "events", "list"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 1
    assert not process.stdout
    assert process.stderr == error_message

    # now same thing but with debug enabled
    command = BBCTL_COMMAND + ["-d", "-u", bogus_server_url, "events", "list"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 1
    assert not process.stdout
    assert len(process.stderr) > 1000
    assert error_message in process.stderr
    assert "[DEBUG] Traceback (most recent call last):" in process.stderr


def test_cli_config():
    TEST_CONFIG_PATH = Path(__file__).parent.parent / "test_config.yml"

    result = subprocess.run(BBCTL_COMMAND + ["server", "current-config"], capture_output=True, text=True)
    assert result.returncode == 0
    config = yaml.safe_load(result.stdout)
    assert config["event_store"]["uri"] == "mongodb://localhost:27017/bbot_eventstore"

    result = subprocess.run(
        BBCTL_COMMAND + ["-c", str(TEST_CONFIG_PATH), "server", "current-config"], capture_output=True, text=True
    )
    assert result.returncode == 0
    config = yaml.safe_load(result.stdout)
    assert config["event_store"]["uri"] == "mongodb://localhost:27017/test_bbot_server_events"
