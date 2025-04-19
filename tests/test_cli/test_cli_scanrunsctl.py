import orjson
import subprocess
from time import sleep

from tests.conftest import BBCTL_COMMAND
from bbot_server.models.scan_models import ScanRun


# TODO: test starting the same scan twice (creating two runs back to back from a single scan)


def test_cli_scan_runs(bbot_server_http, bbot_watchdog, bbot_out_file, bbot_events):
    scan1_out_file, scan2_out_file = bbot_out_file
    scan1_events, scan2_events = bbot_events
    scan1_name = scan1_events[0].data_json["name"]
    scan2_name = scan2_events[0].data_json["name"]

    # we shouldn't have any scan runs yet
    command = BBCTL_COMMAND + ["scan", "runs", "list", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.stdout == ""

    # ingest the first half from stdin
    subprocess.run(BBCTL_COMMAND + ["event", "ingest"], input=scan1_out_file, capture_output=True, text=True)

    sleep(1)

    # make sure the scan run was created
    process = subprocess.run(BBCTL_COMMAND + ["scan", "runs", "list", "--json"], capture_output=True, text=True)
    out_scan_runs = [ScanRun(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert out_scan_runs and len(out_scan_runs) == 1
    assert {s.name for s in out_scan_runs} == {scan1_name}

    # ingest the other half from stdin
    subprocess.run(BBCTL_COMMAND + ["event", "ingest"], input=scan2_out_file, capture_output=True, text=True)

    sleep(1)

    # make sure the scan run was created
    process = subprocess.run(BBCTL_COMMAND + ["scan", "runs", "list", "--json"], capture_output=True, text=True)
    out_scan_runs = [ScanRun(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert out_scan_runs and len(out_scan_runs) == 2
    assert {s.name for s in out_scan_runs} == {scan1_name, scan2_name}

    # test text version
    process = subprocess.run(BBCTL_COMMAND + ["scan", "runs", "list"], capture_output=True, text=True)
    assert len([l for l in process.stdout.splitlines() if l.strip()]) == 6
    assert scan1_name in process.stdout
    assert scan2_name in process.stdout

    # test csv version
    process = subprocess.run(BBCTL_COMMAND + ["scan", "runs", "list", "--csv"], capture_output=True, text=True)
    assert len([l for l in process.stdout.splitlines() if l.strip()]) == 3
    assert scan1_name in process.stdout
    assert scan2_name in process.stdout
