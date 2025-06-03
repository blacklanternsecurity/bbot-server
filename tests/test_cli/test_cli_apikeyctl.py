import orjson
import subprocess

import bbot_server.config as bbcfg
from tests.conftest import BBCTL_COMMAND


def test_cli_apikeyctl(bbot_server_http):
    # we shouldn't have any presets yet
    command = BBCTL_COMMAND + ["server", "apikey", "list", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    print(process.stdout)
    print(process.stderr)
    assert process.returncode == 0
    output = orjson.loads(process.stdout)
    assert output
    assert isinstance(output, list)
    assert len(output) == 1
    assert output == [bbcfg.get_api_key()]
