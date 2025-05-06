# tests for basic CLI functionality like debugging, etc.

import yaml
import subprocess

from tests.conftest import BBCTL_COMMAND, BBOT_SERVER_TEST_DIR


# make sure error handling works properly
def test_cli_debugging():
    bogus_server_url = "http://localhost:58777"
    error_message = f"[ERROR] Error making GET request -> {bogus_server_url}/events/?archived=False&active=True: All connection attempts failed\n"

    # induce an error with a bogus server URL
    command = BBCTL_COMMAND + ["-u", bogus_server_url, "event", "list"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 1
    assert not process.stdout
    assert process.stderr.endswith(error_message)

    # now same thing but with debug enabled
    command = BBCTL_COMMAND + ["-d", "-u", bogus_server_url, "event", "list"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 1
    assert not process.stdout
    assert len(process.stderr) > 1000
    assert error_message in process.stderr
    assert "[DEBUG] Traceback (most recent call last):" in process.stderr


def test_cli_config():
    result = subprocess.run(BBCTL_COMMAND + ["server", "current-config"], capture_output=True, text=True)
    assert result.returncode == 0
    config = yaml.safe_load(result.stdout)
    assert config["event_store"]["uri"] == "mongodb://localhost:27017/test_bbot_server_events"

    yaml_config_str = """
event_store:
  uri: mongodb://localhost:27017/asdf
"""
    temp_config_path = BBOT_SERVER_TEST_DIR / "test_bbot_server_config.yml"
    with open(temp_config_path, "w") as f:
        f.write(yaml_config_str)

    result = subprocess.run(
        BBCTL_COMMAND + ["-c", str(temp_config_path), "server", "current-config"], capture_output=True, text=True
    )
    assert result.returncode == 0
    config = yaml.safe_load(result.stdout)
    assert config["event_store"]["uri"] == "mongodb://localhost:27017/asdf"
    temp_config_path.unlink()
