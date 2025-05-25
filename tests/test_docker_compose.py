# A sanity check to test basic first-time setup

import os
import json
import yaml
import time
import pytest
import subprocess
from pathlib import Path

from .conftest import BBOT_SERVER_TEST_DIR


project_root = Path(__file__).parent.parent
custom_config_file = BBOT_SERVER_TEST_DIR / "docker_test_config.yml"

# we typically only want to run this on CI
# to avoid messing with the user's existing bbot server data / api keys
pytestmark = pytest.mark.skipif(
    os.environ.get("BBOT_SERVER_TEST_DOCKER_COMPOSE", "false").lower() != "true",
    reason="BBOT_SERVER_TEST_DOCKER_COMPOSE is not set to true",
)


def test_docker_compose_userexperience():
    try:
        # make sure docker compose is down
        result = subprocess.run(
            ["docker", "compose", "down"],
            cwd=project_root,
        )
        assert result.returncode == 0

        docker_compose_file = project_root / "compose.yml"
        assert docker_compose_file.exists()

        # create a blank config file just for this test
        custom_config_file.unlink(missing_ok=True)
        custom_config_file.write_text("testasdf: testasdf")

        BBCTL_COMMAND = ["poetry", "run", "bbctl", "--config", str(custom_config_file)]

        # current config should have no api key or valid api keys
        result = subprocess.run(
            BBCTL_COMMAND + ["--current-config"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        config = yaml.safe_load(result.stdout)
        assert config.get("testasdf", "") == "testasdf"
        assert not config.get("api_key", "")
        assert not config.get("valid_api_keys", [])

        # try listing assets
        # this should fail because we don't have an API key
        result = subprocess.run(
            BBCTL_COMMAND + ["asset", "stats"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Please set `api_key` in your config file" in result.stderr

        # even with API key, this should fail because docker compose isn't running
        custom_config_file.write_text(
            "api_key: deadbeef-dead-beef-dead-beefdeadbeef:deadbeef-dead-beef-dead-beefdeadbeef"
        )
        result = subprocess.run(
            BBCTL_COMMAND + ["asset", "stats"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Error making GET request" in result.stderr

        # clear config file
        custom_config_file.write_text("")

        # make sure we don't have an api key
        result = subprocess.run(
            BBCTL_COMMAND + ["--current-config"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        config = yaml.safe_load(result.stdout)
        assert not config.get("api_key", "")

        # start docker compose
        result = subprocess.run(
            BBCTL_COMMAND + ["server", "start"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "First run detected" in result.stderr

        # is api key listed now?
        result = subprocess.run(
            BBCTL_COMMAND + ["--current-config"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        config = yaml.safe_load(result.stdout)
        docker_api_key = config.get("api_key", "")
        # load api key from our custom config file
        our_api_key = yaml.safe_load(custom_config_file.read_text()).get("api_key", "")
        assert our_api_key
        assert docker_api_key[:20] == our_api_key[:20]

        for _ in range(120):
            # we should be able to list assets now
            result = subprocess.run(
                BBCTL_COMMAND + ["asset", "stats"],
                cwd=project_root,
                capture_output=True,
                text=True,
            )
            assert not "Invalid API key" in result.stderr
            if result.returncode == 0 and json.loads(result.stdout) == {}:
                break
            time.sleep(0.5)
        else:
            assert False, f"Failed to list assets, stdout: {result.stdout}, stderr: {result.stderr}"

    finally:
        # stop docker compose
        result = subprocess.run(
            ["docker", "compose", "down"],
            cwd=project_root,
        )
        assert result.returncode == 0

        # remove the custom config file
        custom_config_file.unlink(missing_ok=True)


def test_docker_compose_custom_config():
    # create a blank config file just for this test
    custom_config_file.unlink(missing_ok=True)
    custom_config_file.write_text("test1234: test4321")

    # can we read it outside of docker compose?
    BBCTL_COMMAND = ["poetry", "run", "bbctl", "--config", str(custom_config_file)]
    result = subprocess.run(
        BBCTL_COMMAND + ["--current-config"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    config = yaml.safe_load(result.stdout)
    assert config.get("test1234", "") == "test4321"

    # if we don't pass --config, the docker container should use the default config
    result = subprocess.run(
        ["poetry", "run", "bbctl", "server", "run-docker-compose", "run", "server", "bbctl", "--current-config"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "uri: mongodb://mongodb:27017/bbot_eventstore" in result.stdout
    assert not "test1234: test4321" in result.stdout

    # if we do pass --config, it should use the custom config
    result = subprocess.run(
        BBCTL_COMMAND + ["server", "run-docker-compose", "run", "server", "bbctl", "--current-config"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "test1234: test4321" in result.stdout

    custom_config_file.unlink(missing_ok=True)


def test_docker_compose_authentication():
    # create a blank config file just for this test
    custom_config_file.unlink(missing_ok=True)
    custom_config_file.write_text("")

    BBCTL_COMMAND = ["poetry", "run", "bbctl", "--config", str(custom_config_file)]

    try:
        # make sure docker compose is down
        result = subprocess.run(
            ["docker", "compose", "down"],
            cwd=project_root,
        )
        assert result.returncode == 0

        # start docker compose
        result = subprocess.run(
            BBCTL_COMMAND + ["server", "start"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        for _ in range(120):
            # docker should detect first run and write a new api key to the custom config file
            custom_config = yaml.safe_load(custom_config_file.read_text())
            if custom_config:
                api_key = custom_config.get("api_key", "")
                valid_secrets = custom_config.get("valid_secrets", {})
                secret_id = api_key.split(":")[0]
                if api_key and valid_secrets and secret_id in valid_secrets:
                    break
            time.sleep(0.5)
        else:
            assert False, f"Failed to get api key, stdout: {result.stdout}, stderr: {result.stderr}"

        # without the API key, auth should fail
        for _ in range(120):
            result = subprocess.run(
                ["poetry", "run", "bbctl", "asset", "stats"],
                cwd=project_root,
                capture_output=True,
                text=True,
            )
            if "Invalid API key" in result.stderr or "No API key found" in result.stderr:
                break
            time.sleep(0.5)
        else:
            assert False, f"We should have received an auth error, stdout: {result.stdout}, stderr: {result.stderr}"

        # but with the key, we should be able to list assets
        result = subprocess.run(
            BBCTL_COMMAND + ["asset", "stats"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout == "{}\n"

    finally:
        # stop docker compose
        result = subprocess.run(
            ["docker", "compose", "down"],
            cwd=project_root,
        )
        assert result.returncode == 0

        # remove the custom config file
        custom_config_file.unlink(missing_ok=True)


# test the --listen flag and --port flags
def test_docker_compose_listening_interface():
    try:
        # create a blank config file just for this test
        custom_config_file.unlink(missing_ok=True)
        custom_config_file.write_text("url: http://127.0.0.1:8807/v1/")

        BBCTL_COMMAND = ["poetry", "run", "bbctl", "--config", str(custom_config_file)]

        # start docker compose
        result = subprocess.run(
            BBCTL_COMMAND + ["server", "start"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        # we should be able to list assets
        for _ in range(120):
            result = subprocess.run(
                BBCTL_COMMAND + ["asset", "stats"],
                cwd=project_root,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and json.loads(result.stdout) == {}:
                break
            time.sleep(0.5)
        else:
            assert False, f"Failed to list assets, stdout: {result.stdout}, stderr: {result.stderr}"

        # but if we try 127.0.0.2, it should fail
        custom_config_file.write_text("url: http://127.0.0.2:8807/v1/")
        result = subprocess.run(
            BBCTL_COMMAND + ["asset", "stats"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Error making GET request" in result.stderr

        # docker compose down
        result = subprocess.run(
            ["docker", "compose", "down"],
            cwd=project_root,
        )
        assert result.returncode == 0

        # this time, we change up the interface
        result = subprocess.run(
            BBCTL_COMMAND + ["server", "start", "--listen", "127.0.0.2"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        # we should be able to list assets
        for _ in range(120):
            result = subprocess.run(
                BBCTL_COMMAND + ["asset", "stats"],
                cwd=project_root,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and json.loads(result.stdout) == {}:
                break
            time.sleep(0.5)
        else:
            assert False, f"Failed to list assets, stdout: {result.stdout}, stderr: {result.stderr}"

        # but 127.0.0.1 should fail
        custom_config_file.write_text("url: http://127.0.0.1:8807/v1/")
        result = subprocess.run(
            BBCTL_COMMAND + ["asset", "stats"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Error making GET request" in result.stderr

    finally:
        # stop docker compose
        result = subprocess.run(
            ["docker", "compose", "down"],
            cwd=project_root,
        )
