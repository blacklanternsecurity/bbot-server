import orjson
import subprocess
from time import sleep

from tests.conftest import BBCTL_COMMAND
from bbot_server.assets import Asset


scan1_expected_hosts = {
    "a.com",
    "www.evilcorp.com",
    "cname.evilcorp.com",
    "127.0.0.1",
    "www2.evilcorp.com",
    "api.evilcorp.com",
    "5.6.7.8",
    "1.2.3.4",
    "evilcorp.com",
    "localhost.evilcorp.com",
}

scan2_expected_hosts = {
    "a.com",
    "b.com",
    "www.evilcorp.com",
    "cname.evilcorp.com",
    "127.0.0.1",
    "127.0.0.2",
    "www2.evilcorp.com",
    "api.evilcorp.com",
    "5.6.7.8",
    "1.2.3.4",
    "evilcorp.com",
    "localhost.evilcorp.com",
}


def test_cli_assetctl(bbot_server_http, bbot_watchdog, bbot_out_file, bbot_events):
    scan1_out_file, scan2_out_file = bbot_out_file
    scan1_events, scan2_events = bbot_events

    # we shouldn't have any assets yet
    command = BBCTL_COMMAND + ["asset", "list", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.stdout == ""

    # ingest the first half from stdin
    subprocess.run(BBCTL_COMMAND + ["event", "ingest"], input=scan1_out_file, capture_output=True, text=True)

    sleep(1)

    # make sure the assets were created
    process = subprocess.run(BBCTL_COMMAND + ["asset", "list", "--json"], capture_output=True, text=True)
    assets = [Asset(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert assets
    assert {a.host for a in assets} == scan1_expected_hosts

    # ingest the other half from stdin
    subprocess.run(BBCTL_COMMAND + ["event", "ingest"], input=scan2_out_file, capture_output=True, text=True)

    sleep(1)

    # make sure the assets were created
    process = subprocess.run(BBCTL_COMMAND + ["asset", "list", "--json"], capture_output=True, text=True)
    assets = [Asset(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert assets
    assert {a.host for a in assets} == scan2_expected_hosts

    # test csv version
    process = subprocess.run(BBCTL_COMMAND + ["asset", "list", "--csv"], capture_output=True, text=True)
    hosts = {l.split(",")[0] for l in process.stdout.splitlines()[1:]}
    assert hosts == scan2_expected_hosts

    # test txt version
    process = subprocess.run(BBCTL_COMMAND + ["asset", "list"], capture_output=True, text=True)
    assert len([l for l in process.stdout.splitlines() if l.strip()]) == len(scan2_expected_hosts) + 4

    return

    # create a target
    subprocess.run(BBCTL_COMMAND + ["target", "create", "test-target"], capture_output=True, text=True)

    # create a scan
    subprocess.run(
        BBCTL_COMMAND + ["scan", "create", "test-scan", "--target", "test-target"], capture_output=True, text=True
    )
