# A sanity check to test basic first-time setup

import os
import sys
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


def bbctl_command(config_file=None):
    cmd = ["uv", "run", "bbctl"]
    if config_file:
        cmd += ["--config", str(config_file)]
    return cmd


def server_args(dev=True):
    """Return the server subcommand args with or without --dev."""
    if dev:
        return ["server", "--dev"]
    return ["server"]


@contextmanager
def docker_test_env(dev=True, reset_config=True, docker_down_first=True, cleanup_config=True):
    """
    Context manager for docker compose tests.

    Args:
        dev: Use dev compose (build from source) vs production compose (pull from Docker Hub)
        reset_config: Reset config file at start
        docker_down_first: Run docker compose down before test
        cleanup_config: Delete custom config file after test
    """
    srv = server_args(dev)

    # Setup
    if reset_config:
        reset_config_file()

    if docker_down_first:
        subprocess.run(
            bbctl_command(custom_config_file) + srv + ["down"],
            cwd=project_root,
        )

    try:
        yield
    finally:
        # Cleanup - print logs if test failed
        if sys.exc_info()[0] is not None:
            print_docker_logs(dev=dev)

        # Always stop docker compose
        subprocess.run(
            bbctl_command(custom_config_file) + srv + ["down"],
            cwd=project_root,
        )

        # Remove the custom config file
        if cleanup_config:
            custom_config_file.unlink(missing_ok=True)


def print_docker_logs(dev=True):
    """Helper to print docker compose logs"""
    print("\n" + "=" * 80)
    print("TEST FAILED - Docker Compose Logs:")
    print("=" * 80)
    result = subprocess.run(
        bbctl_command(custom_config_file) + server_args(dev) + ["logs"],
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


def start_server(bbctl_cmd, dev=True, extra_args=None):
    """Start the server and return the result. Asserts success."""
    cmd = bbctl_cmd + server_args(dev) + ["start"] + (extra_args or [])
    result = subprocess.run(
        cmd,
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Failed to start server: {result.stderr}"
    return result


def wait_for_server(bbctl_cmd, timeout_seconds=60):
    """Wait for the server to become healthy (asset stats returns 200)."""
    for _ in range(timeout_seconds * 2):
        result = subprocess.run(
            bbctl_cmd + ["asset", "stats"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result
        time.sleep(0.5)
    assert False, (
        f"Server did not become healthy within {timeout_seconds}s, stdout: {result.stdout}, stderr: {result.stderr}"
    )


# we typically only want to run this on CI
# to avoid messing with the user's existing bbot server data / api keys
pytestmark = pytest.mark.skipif(
    os.environ.get("BBOT_SERVER_TEST_DOCKER_COMPOSE", "false").lower() != "true",
    reason="BBOT_SERVER_TEST_DOCKER_COMPOSE is not set to true",
)


def test_docker_compose_userexperience():
    """
    A basic up/down test to make sure bbot server is working with docker compose
    """
    with docker_test_env(dev=True, reset_config=False, docker_down_first=True):
        docker_compose_file = project_root / "compose.yml"
        assert docker_compose_file.exists()

        # create a blank config file just for this test
        custom_config_file.unlink(missing_ok=True)
        custom_config_file.write_text("testasdf: testasdf")

        BBCTL_COMMAND = bbctl_command(custom_config_file)

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
        result = start_server(BBCTL_COMMAND, dev=True)
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

        wait_for_server(BBCTL_COMMAND)


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
    BBCTL_COMMAND = bbctl_command(custom_config_file)
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
        ["uv", "run", "bbctl", "server", "--dev", "compose", "run", "server", "bbctl", "--current-config"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "uri: mongodb://mongodb:27017/bbot" in result.stdout
    assert not "test1234: test4321" in result.stdout

    # if we do pass --config, it should use the custom config
    result = subprocess.run(
        BBCTL_COMMAND + ["server", "--dev", "compose", "run", "server", "bbctl", "--current-config"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "test1234: test4321" in result.stdout

    custom_config_file.unlink(missing_ok=True)


# test the --listen flag and --port flags
def test_docker_compose_listening_interface():
    with docker_test_env(dev=True, reset_config=True, docker_down_first=True):
        # create a blank config file just for this test
        with open(custom_config_file, "a") as f:
            f.write("\nurl: http://127.0.0.1:8807/v1/\n")

        BBCTL_COMMAND = bbctl_command(custom_config_file)

        # start docker compose
        start_server(BBCTL_COMMAND, dev=True)

        # we should be able to list assets
        wait_for_server(BBCTL_COMMAND)

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
        subprocess.run(
            BBCTL_COMMAND + server_args(dev=True) + ["down"],
            cwd=project_root,
        )

        # this time, we change up the interface
        start_server(BBCTL_COMMAND, dev=True, extra_args=["--listen", "127.0.0.2"])

        # we should be able to list assets
        wait_for_server(BBCTL_COMMAND)

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

    BBCTL_COMMAND = bbctl_command(custom_config_file)

    with docker_test_env(dev=True, reset_config=True, docker_down_first=True):
        # start docker compose
        start_server(BBCTL_COMMAND, dev=True)

        for _ in range(120):
            # docker should detect first run and write a new api key to the custom config file
            custom_config = yaml.safe_load(custom_config_file.read_text())
            if custom_config:
                api_keys = custom_config.get("api_keys", [])
                if api_keys:
                    break
            time.sleep(0.5)
        else:
            assert False, f"Failed to get api key"

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

    BBCTL_COMMAND = bbctl_command(custom_config_file)

    with docker_test_env(dev=True, reset_config=True, docker_down_first=True):
        start_server(BBCTL_COMMAND, dev=True, extra_args=["--no-authentication"])

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


def test_docker_compose_production():
    """
    Smoke test for the production compose (pulls from Docker Hub).
    Starts the server, waits for healthy, queries asset stats.
    """
    with docker_test_env(dev=False, reset_config=True, docker_down_first=True):
        BBCTL_COMMAND = bbctl_command(custom_config_file)

        # start production compose (no --dev, pulls from Docker Hub)
        result = start_server(BBCTL_COMMAND, dev=False)
        assert "First run detected" in result.stderr

        # wait for server to be healthy
        wait_for_server(BBCTL_COMMAND)

        # verify asset stats returns successfully
        result = subprocess.run(
            BBCTL_COMMAND + ["asset", "stats"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
