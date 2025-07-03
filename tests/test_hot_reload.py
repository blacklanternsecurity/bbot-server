import time
import httpx
import signal
import subprocess
from contextlib import suppress

from .conftest import BBCTL_COMMAND
import bbot_server.config as bbcfg


def test_hot_reload():
    API_KEY = bbcfg.get_api_key()

    # start API server in background
    process = subprocess.Popen(
        BBCTL_COMMAND + ["server", "start", "--api-only", "--reload"],
    )

    for _ in range(300):
        with suppress(Exception):
            response = httpx.get(f"http://localhost:8807/v1/assets/hosts", headers={"X-API-Key": API_KEY})
            if getattr(response, "status_code", 0) == 200:
                break
        time.sleep(0.1)
    else:
        assert False, "Failed to start bbot server with --reload"

    # kill process, first with SIGINT, then with SIGKILL
    process.send_signal(signal.SIGINT)
    process.wait(timeout=1)
    if process.poll() is None:
        process.send_signal(signal.SIGKILL)
        process.wait(timeout=1)
