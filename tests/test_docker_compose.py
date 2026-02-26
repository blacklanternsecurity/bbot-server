# A sanity check to test basic first-time setup

import os
import sys
import json
import yaml
import time
import httpx
import pytest
import subprocess
from pathlib import Path
from shutil import copyfile
from contextlib import contextmanager

from .conftest import BBOT_SERVER_TEST_DIR


project_root = Path(__file__).parent.parent
custom_config_file = BBOT_SERVER_TEST_DIR / "docker_test_config.yml"


def reset_config_file():
    copyfile(Path(__file__).parent / "test_config_docker.yml", custom_config_file)


@contextmanager
def docker_test_env(reset_config=True, docker_down_first=True, cleanup_config=True):
    """
    Context manager for docker compose tests.

    Args:
        reset_config: Reset config file at start
        docker_down_first: Run docker compose down before test
        cleanup_config: Delete custom config file after test
    """
    # Setup
    if reset_config:
        reset_config_file()

    if docker_down_first:
        result = subprocess.run(
            ["docker", "compose", "down"],
            cwd=project_root,
        )
        assert result.returncode == 0

    try:
        yield
    finally:
        # Cleanup - print logs if test failed
        if sys.exc_info()[0] is not None:
            print_docker_logs()

        # Always stop docker compose
        subprocess.run(
            ["docker", "compose", "down"],
            cwd=project_root,
        )

        # Remove the custom config file
        if cleanup_config:
            custom_config_file.unlink(missing_ok=True)


# we typically only want to run this on CI
# to avoid messing with the user's existing bbot server data / api keys
pytestmark = pytest.mark.skipif(
    os.environ.get("BBOT_SERVER_TEST_DOCKER_COMPOSE", "false").lower() != "true",
    reason="BBOT_SERVER_TEST_DOCKER_COMPOSE is not set to true",
)


def print_docker_logs():
    """Helper to print docker compose logs"""
    print("\n" + "=" * 80)
    print("TEST FAILED - Docker Compose Logs:")
    print("=" * 80)
    result = subprocess.run(
        ["docker", "compose", "logs", "--no-color"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(result.stdout)
        if result.stderr:
            print("\nSTDERR:")
            print(result.stderr)
    else:
        print(f"Failed to get docker compose logs (exit code {result.returncode}): {result.stderr}")
    print("=" * 80 + "\n")


def test_docker_compose_userexperience():
    """
    A basic up/down test to make sure bbot server is working with docker compose
    """
    with docker_test_env(reset_config=False, docker_down_first=True):
        # build it
        # result = subprocess.run(
        #     ["docker", "compose", "build"],
        #     cwd=project_root,
        # )
        # assert result.returncode == 0

        docker_compose_file = project_root / "compose.yml"
        assert docker_compose_file.exists()

        # create a blank config file just for this test
        custom_config_file.unlink(missing_ok=True)
        custom_config_file.write_text("testasdf: testasdf")

        BBCTL_COMMAND = ["uv", "run", "bbctl", "--config", str(custom_config_file)]

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
        assert not config.get("api_keys", [])

        # try listing assets
        # this should fail because we don't have an API key
        result = subprocess.run(
            BBCTL_COMMAND + ["asset", "stats"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Please set `api_keys` in your config file" in result.stderr

        # even with API key, this should fail because docker compose isn't running
        custom_config_file.write_text('api_keys: ["deadbeef-dead-beef-dead-beefdeadbeef"]')
        result = subprocess.run(
            BBCTL_COMMAND + ["asset", "stats"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Error making GET request" in result.stderr

        reset_config_file()

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
        assert not config.get("api_keys", [])

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
        docker_api_key = config.get("api_keys", [])
        assert docker_api_key
        assert len(docker_api_key) == 1
        docker_api_key = docker_api_key[0]
        # load api key from our custom config file
        our_api_key = yaml.safe_load(custom_config_file.read_text()).get("api_keys", [])
        assert our_api_key
        assert len(our_api_key) == 1
        our_api_key = our_api_key[0]
        assert docker_api_key[:20] == our_api_key[:20]

        for _ in range(120):
            # we should be able to list assets now
            command = BBCTL_COMMAND + ["asset", "stats"]
            print(f"command: {' '.join(command)}")
            result = subprocess.run(
                command,
                cwd=project_root,
                capture_output=True,
                text=True,
            )
            print(f"result: {result.returncode}, stdout: {result.stdout}, stderr: {result.stderr}")
            assert not "Invalid API key" in result.stderr
            if result.returncode == 0 and json.loads(result.stdout) == {}:
                break
            time.sleep(0.5)
        else:
            assert False, f"Failed to list assets, stdout: {result.stdout}, stderr: {result.stderr}"


def test_docker_compose_custom_config():
    # delete config env var for this test
    os.environ.pop("BBOT_SERVER_CONFIG", None)

    # Ensure the default host config path exists so Docker bind-mounts a file
    # (not a root-owned directory) when BBOT_SERVER_CONFIG is unset
    default_config = Path.home() / ".config" / "bbot_server" / "config.yml"
    default_config.parent.mkdir(parents=True, exist_ok=True)
    if not default_config.exists():
        default_config.touch()

    # create a blank config file just for this test
    custom_config_file.unlink(missing_ok=True)
    custom_config_file.write_text("test1234: test4321")

    # can we read it outside of docker compose?
    BBCTL_COMMAND = ["uv", "run", "bbctl", "--config", str(custom_config_file)]
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
        ["uv", "run", "bbctl", "server", "compose", "run", "server", "bbctl", "--current-config"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "uri: mongodb://mongodb:27017/bbot_eventstore" in result.stdout
    assert not "test1234: test4321" in result.stdout

    # if we do pass --config, it should use the custom config
    result = subprocess.run(
        BBCTL_COMMAND + ["server", "compose", "run", "server", "bbctl", "--current-config"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "test1234: test4321" in result.stdout

    custom_config_file.unlink(missing_ok=True)


# test the --listen flag and --port flags
def test_docker_compose_listening_interface():
    with docker_test_env(reset_config=True, docker_down_first=True):
        # create a blank config file just for this test
        with open(custom_config_file, "a") as f:
            f.write("\nurl: http://127.0.0.1:8807/v1/\n")

        BBCTL_COMMAND = ["uv", "run", "bbctl", "--config", str(custom_config_file)]

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

        # replace the url key with 127.0.0.2
        config_content = custom_config_file.read_text()
        new_config_content = config_content.replace("url: http://127.0.0.1:8807/v1/", "url: http://127.0.0.2:8807/v1/")
        custom_config_file.write_text(new_config_content)
        # but if we try 127.0.0.2, it should fail
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

        # replace the url key with 127.0.0.1
        config_content = custom_config_file.read_text()
        new_config_content = config_content.replace("url: http://127.0.0.2:8807/v1/", "url: http://127.0.0.1:8807/v1/")
        custom_config_file.write_text(new_config_content)

        # but 127.0.0.1 should fail
        result = subprocess.run(
            BBCTL_COMMAND + ["asset", "stats"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Error making GET request" in result.stderr


def test_docker_compose_authentication():
    # create a blank config file just for this test
    custom_config_file.unlink(missing_ok=True)
    custom_config_file.write_text("")

    BBCTL_COMMAND = ["uv", "run", "bbctl", "--config", str(custom_config_file)]

    with docker_test_env(reset_config=True, docker_down_first=True):
        # start docker compose
        result = subprocess.run(
            BBCTL_COMMAND + ["server", "start"],
            cwd=project_root,
        )
        assert result.returncode == 0

        for _ in range(120):
            # docker should detect first run and write a new api key to the custom config file
            custom_config = yaml.safe_load(custom_config_file.read_text())
            if custom_config:
                api_keys = custom_config.get("api_keys", [])
                if api_keys:
                    break
            time.sleep(0.5)
        else:
            assert False, f"Failed to get api key, stdout: {result.stdout}, stderr: {result.stderr}"

        # without the API key, auth should fail
        for _ in range(120):
            result = subprocess.run(
                ["uv", "run", "bbctl", "asset", "stats"],
                cwd=project_root,
                capture_output=True,
                text=True,
            )
            if "No API keys found" in result.stderr:
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


def test_docker_compose_no_authentication():
    """
    Tests to make sure when we run:
        bbctl server start --no-authentication
    that we can curl the API without an API key
    """
    custom_config_file.unlink(missing_ok=True)

    BBCTL_COMMAND = ["uv", "run", "bbctl", "--config", str(custom_config_file)]

    with docker_test_env(reset_config=True, docker_down_first=True):
        result = subprocess.run(
            BBCTL_COMMAND + ["server", "start", "--no-authentication"],
            cwd=project_root,
        )
        assert result.returncode == 0

        for _ in range(120):
            try:
                response = httpx.get("http://127.0.0.1:8807/v1/assets/hosts")
                if response.status_code == 200:
                    break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            assert False, (
                f"Expected 200 OK without auth, got: {response.status_code if 'response' in locals() else 'no response'}"
            )
