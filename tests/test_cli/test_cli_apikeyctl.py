import orjson
import subprocess

from bbot_server.config import BBOT_SERVER_CONFIG as bbcfg
from tests.conftest import BBCTL_COMMAND


def test_cli_apikeyctl(bbot_server_http):
    api_key = bbcfg.get_api_key()
    assert api_key
    api_key = str(api_key)

    # text output
    command = BBCTL_COMMAND + ["server", "apikey", "list"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert api_key in process.stdout

    # JSON output
    command = BBCTL_COMMAND + ["server", "apikey", "list", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    output = orjson.loads(process.stdout)
    assert output
    assert isinstance(output, list)
    assert len(output) == 1
    assert output == [api_key]
