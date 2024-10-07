import pytest

# from pytest_httpserver import HTTPServer

from bbot.core import CORE

test_home = "/tmp/.bbotio_test"

CORE.custom_config["home"] = test_home

from bbot_server import config
from pathlib import Path

config.home = Path(test_home)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_sessionfinish(session, exitstatus):
    import shutil

    # clean up temporary test dir
    shutil.rmtree(test_home, ignore_errors=True)

    yield


# @pytest.fixture
# def bbot_httpserver():
#     server = HTTPServer(host="127.0.0.1", port=8888)
#     server.start()

#     server.expect_request("/").respond_with_data("OK")

#     yield server

#     server.clear()
#     if server.is_running():
#         server.stop()

#     # this is to check if the client has made any request where no
#     # `assert_request` was called on it from the test

#     server.check_assertions()
#     server.clear()


import httpx
from time import sleep
import multiprocessing
from bbot_server.server import run_server


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
    while 1:
        try:
            response = httpx.get("http://127.0.0.1:7777/docs")
            if response.status_code == 200:
                break
        except httpx.HTTPError:
            sleep(0.01)

    yield

    # Teardown: stop the server process
    proc.terminate()
    proc.join()
