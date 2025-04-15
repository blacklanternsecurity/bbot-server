import orjson
import subprocess
from time import sleep
from pathlib import Path

from bbot.models.pydantic import Event

from tests.conftest import BBCTL_COMMAND


def test_cli_events(bbot_server_http, bbot_watchdog, bbot_out_file, bbot_events):
    scan1_out_file, scan2_out_file = bbot_out_file
    scan1_events, scan2_events = bbot_events

    # we shouldn't have any events yet
    command = BBCTL_COMMAND + ["events", "list", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    print(" ".join(command))
    assert process.stdout == ""

    # ingest bbot events from file
    json_file = Path("/tmp/.bbot_server_test/events.json")
    with open(json_file, "w") as f:
        f.write(scan1_out_file)

    process = subprocess.run(
        BBCTL_COMMAND + ["events", "ingest", "-f", str(json_file)], capture_output=True, text=True
    )
    assert process.returncode == 0
    assert process.stdout == ""
    assert process.stderr == "[INFO] Ingested 10 events\n[INFO] Ingested 20 events\n"

    sleep(1)

    # make sure all the events made it into the database
    process = subprocess.run(BBCTL_COMMAND + ["events", "list", "--json"], capture_output=True, text=True)
    out_events = [Event(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert out_events and len(out_events) == len(scan1_events)

    # ingest the other half from stdin
    process = subprocess.run(
        BBCTL_COMMAND + ["events", "ingest"], input=scan2_out_file, capture_output=True, text=True
    )
    assert process.returncode == 0
    assert process.stdout == ""
    assert process.stderr == "[INFO] Ingested 10 events\n[INFO] Ingested 20 events\n"

    sleep(1)

    # make sure all the events made it into the database
    process = subprocess.run(BBCTL_COMMAND + ["events", "list", "--json"], capture_output=True, text=True)
    out_events = [Event(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert out_events and len(out_events) == len(scan1_events + scan2_events)

    json_file.unlink()
