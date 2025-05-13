import orjson
import subprocess
from time import sleep

from bbot.models.pydantic import Event

from tests.conftest import BBCTL_COMMAND, INGEST_PROCESSING_DELAY, BBOT_SERVER_TEST_DIR
from bbot_server.models.scan_models import Scan


def test_cli_scan_start(bbot_server_http, bbot_watchdog, bbot_agent):
    # we shouldn't have any scans yet
    command = BBCTL_COMMAND + ["scan", "list", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)

    target_file = BBOT_SERVER_TEST_DIR / "test_target.txt"
    target_file.unlink(missing_ok=True)
    target_file.write_text("127.0.0.1")

    preset_file = BBOT_SERVER_TEST_DIR / "test_preset.yml"
    preset_file.unlink(missing_ok=True)
    preset_file.write_text(
        """
name: thepreset
description: thepreset description

debug: true
"""
    )

    # create a target
    process = subprocess.run(
        BBCTL_COMMAND
        + [
            "scan",
            "target",
            "create",
            "--seeds",
            str(target_file),
            "--name",
            "thetarget",
            "--description",
            "thetarget description",
        ],
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0
    assert "Target created successfully" in process.stderr

    # get the target
    process = subprocess.run(BBCTL_COMMAND + ["scan", "target", "get", "thetarget"], capture_output=True, text=True)
    assert process.returncode == 0
    target = orjson.loads(process.stdout)
    assert target["name"] == "thetarget"

    # create a preset
    process = subprocess.run(
        BBCTL_COMMAND + ["scan", "preset", "create", str(preset_file)], capture_output=True, text=True
    )
    assert process.returncode == 0
    assert "Preset created successfully" in process.stderr

    # get the preset
    process = subprocess.run(BBCTL_COMMAND + ["scan", "preset", "get", "thepreset"], capture_output=True, text=True)
    assert process.returncode == 0
    preset = orjson.loads(process.stdout)
    assert preset["name"] == "thepreset"
    assert preset["description"] == "thepreset description"
    assert preset["preset"]["debug"] == True

    # now that we have a target and preset, we can start a scan
    process = subprocess.run(
        BBCTL_COMMAND + ["scan", "start", "--name", "demonic_jimmy", "--target", "thetarget", "--preset", "thepreset"],
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0
    assert "Scan queued successfully" in process.stderr

    # list scans
    process = subprocess.run(BBCTL_COMMAND + ["scan", "list", "--json"], capture_output=True, text=True)
    assert process.returncode == 0
    scans = [Scan(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert len(scans) == 1
    assert scans[0].name == "demonic_jimmy"
    assert str(scans[0].preset.id) == preset["id"]
    assert scans[0].description.startswith(
        f"Scan 'demonic_jimmy' queued against target 'thetarget' with preset 'thepreset' at"
    )

    for _ in range(120):
        process = subprocess.run(BBCTL_COMMAND + ["scan", "list", "--json"], capture_output=True, text=True)
        scans = [Scan(**orjson.loads(line)) for line in process.stdout.splitlines()]
        if scans[0].status == "FINISHED":
            break
        sleep(0.5)
    else:
        assert False, f"Scan did not finish in time, scans: {scans}"

    assert len(scans) == 1
    assert scans[0].name == "demonic_jimmy"
    assert scans[0].status == "FINISHED"
    assert scans[0].duration_seconds > 0
    assert scans[0].duration is not None
    assert scans[0].finished_at is not None
    assert scans[0].started_at is not None

    process = subprocess.run(BBCTL_COMMAND + ["event", "list", "--json"], capture_output=True, text=True)
    assert process.returncode == 0
    events = [Event(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert len(events) > 0
    assert "127.0.0.1" in [e.data for e in events]

    # create a duplicate scan
    process = subprocess.run(
        BBCTL_COMMAND + ["scan", "start", "--name", "demonic_jimmy", "--target", "thetarget", "--preset", "thepreset"],
        capture_output=True,
        text=True,
    )
    assert process.returncode == 1
    assert "Scan with name 'demonic_jimmy' already exists" in process.stderr


def test_cli_scan_ingest(bbot_server_http, bbot_watchdog, bbot_out_file, bbot_events):
    scan1_out_file, scan2_out_file = bbot_out_file
    scan1_events, scan2_events = bbot_events
    scan1_name = scan1_events[0].data_json["name"]
    scan2_name = scan2_events[0].data_json["name"]

    # we shouldn't have any scans yet
    command = BBCTL_COMMAND + ["scan", "list", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.stdout == ""

    # ingest the first half from stdin
    subprocess.run(BBCTL_COMMAND + ["event", "ingest"], input=scan1_out_file, capture_output=True, text=True)

    sleep(INGEST_PROCESSING_DELAY)

    # make sure the scan run was created
    process = subprocess.run(BBCTL_COMMAND + ["scan", "list", "--json"], capture_output=True, text=True)
    out_scan_runs = [Scan(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert out_scan_runs and len(out_scan_runs) == 1
    assert {s.name for s in out_scan_runs} == {scan1_name}

    # ingest the other half from stdin
    subprocess.run(BBCTL_COMMAND + ["event", "ingest"], input=scan2_out_file, capture_output=True, text=True)

    sleep(INGEST_PROCESSING_DELAY)

    # make sure the scan run was created
    process = subprocess.run(BBCTL_COMMAND + ["scan", "list", "--json"], capture_output=True, text=True)
    out_scan_runs = [Scan(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert out_scan_runs and len(out_scan_runs) == 2
    assert {s.name for s in out_scan_runs} == {scan1_name, scan2_name}

    # test text version
    process = subprocess.run(BBCTL_COMMAND + ["scan", "list"], capture_output=True, text=True)
    assert scan1_name in process.stdout
    assert scan2_name in process.stdout

    # test csv version
    process = subprocess.run(BBCTL_COMMAND + ["scan", "list", "--csv"], capture_output=True, text=True)
    assert len([l for l in process.stdout.splitlines() if l.strip()]) == 3
    assert scan1_name in process.stdout
    assert scan2_name in process.stdout
