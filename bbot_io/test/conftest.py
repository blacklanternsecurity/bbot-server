import pytest

# from pytest_httpserver import HTTPServer

from bbot.core import CORE

test_home = "/tmp/.bbotio_test"

CORE.custom_config["home"] = test_home


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
