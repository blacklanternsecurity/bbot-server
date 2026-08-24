import orjson
import subprocess
from time import sleep
from pathlib import Path

from bbot.models.pydantic import Event

from tests.conftest import BBCTL_COMMAND, INGEST_PROCESSING_DELAY


def assert_ingest_progress(stderr, num_events):
    # the ingester logs progress every 10 events, counting from zero
    last_milestone = ((num_events - 1) // 10) * 10
    for milestone in range(10, last_milestone + 1, 10):
        assert f"Ingested {milestone:,} events" in stderr
    assert f"Ingested {last_milestone + 10:,} events" not in stderr


def test_cli_events(bbot_server_http, bbot_worker, bbot_out_file, bbot_events):
    scan1_out_file, scan2_out_file = bbot_out_file
    scan1_events, scan2_events = bbot_events

    # we shouldn't have any events yet
    command = BBCTL_COMMAND + ["event", "list", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.stdout == ""

    # ingest bbot events from file
    json_file = Path("/tmp/.bbot_server_test/events.json")
    json_file.unlink(missing_ok=True)
    with open(json_file, "w") as f:
        f.write(scan1_out_file)

    process = subprocess.run(BBCTL_COMMAND + ["event", "ingest", "-f", str(json_file)], capture_output=True, text=True)
    assert process.returncode == 0
    assert process.stdout == ""
    assert_ingest_progress(process.stderr, len(scan1_events))

    sleep(INGEST_PROCESSING_DELAY)

    # make sure all the events made it into the database
    process = subprocess.run(BBCTL_COMMAND + ["event", "list", "--json"], capture_output=True, text=True)
    out_events = [Event(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert out_events and len(out_events) == len(scan1_events)

    # ingest the other half from stdin
    process = subprocess.run(BBCTL_COMMAND + ["event", "ingest"], input=scan2_out_file, capture_output=True, text=True)
    assert process.returncode == 0
    assert process.stdout == ""
    assert_ingest_progress(process.stderr, len(scan2_events))

    sleep(INGEST_PROCESSING_DELAY)

    # make sure all the events made it into the database
    process = subprocess.run(BBCTL_COMMAND + ["event", "list", "--json"], capture_output=True, text=True)
    out_events = [Event(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert out_events and len(out_events) == len(scan1_events + scan2_events)

    json_file.unlink()
