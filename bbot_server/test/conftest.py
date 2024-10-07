import httpx
import pytest
import multiprocessing
from time import sleep
from pathlib import Path

from bbot.core import CORE
from bbot_server import config
from bbot_server.server import run_server

test_home = "/tmp/.bbotio_test"

CORE.custom_config["home"] = test_home

config.home = Path(test_home)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_sessionfinish(session, exitstatus):
    import shutil

    # clean up temporary test dir
    shutil.rmtree(test_home, ignore_errors=True)

    yield


@pytest.fixture(scope="session")
def http_server():
    kwargs = {
        "database": "/tmp/.bbotio_test/test.db",
        "uvicorn_options": {
            "port": 7777,
            "log_level": "info",
            "access_log": True,
        },
    }
    # start bbot server in a separate process
    proc = multiprocessing.Process(target=run_server, daemon=True, args=("sqlite",), kwargs=kwargs)
    proc.start()

    # wait for server to come up
    for i in range(999999):
        try:
            response = httpx.get("http://127.0.0.1:7777/docs")
            if response.status_code == 200:
                break
        except httpx.HTTPError:
            assert i < 100, "Server failed to start within 10 seconds"
            sleep(0.1)

    yield

    # Teardown: stop the server process
    proc.terminate()
    proc.join()


from bbot_server.test._gen_scan_data import gen_scan_data  # noqa
