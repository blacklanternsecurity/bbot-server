import orjson
import subprocess
from time import sleep

from tests.conftest import BBCTL_COMMAND, BBOT_SERVER_TEST_DIR, INGEST_PROCESSING_DELAY
from bbot_server.assets import Asset


scan1_expected_hosts = {
    "evilcorp.azure.com",
    "www.evilcorp.com",
    "cname.evilcorp.com",
    "127.0.0.1",
    "www2.evilcorp.com",
    "api.evilcorp.com",
    "5.6.7.8",
    "1.2.3.4",
    "192.168.1.1",
    "192.168.1.2",
    "evilcorp.com",
    "localhost.evilcorp.com",
    "testevilcorp.com",
    "t1.tech.evilcorp.com",
    "t2.tech.evilcorp.com",
}

scan2_expected_hosts = {
    "evilcorp.azure.com",
    "evilcorp.amazonaws.com",
    "www.evilcorp.com",
    "cname.evilcorp.com",
    "127.0.0.1",
    "127.0.0.2",
    "192.168.1.1",
    "192.168.1.2",
    "www2.evilcorp.com",
    "api.evilcorp.com",
    "5.6.7.8",
    "1.2.3.4",
    "evilcorp.com",
    "localhost.evilcorp.com",
    "testevilcorp.com",
    "t1.tech.evilcorp.com",
    "t2.tech.evilcorp.com",
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

    sleep(INGEST_PROCESSING_DELAY)

    # make sure the assets were created
    process = subprocess.run(BBCTL_COMMAND + ["asset", "list", "--json"], capture_output=True, text=True)
    assets = [Asset(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert assets
    assert {a.host for a in assets} == scan1_expected_hosts

    # ingest the other half from stdin
    subprocess.run(BBCTL_COMMAND + ["event", "ingest"], input=scan2_out_file, capture_output=True, text=True)

    sleep(INGEST_PROCESSING_DELAY)

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
    assert process.returncode == 0
    assert "www.evil" in process.stdout

    # test target filtering

    target_file = BBOT_SERVER_TEST_DIR / "seeds.txt"
    target_file.write_text("evilcorp.com\n127.0.0.0/30")
    blacklist_file = BBOT_SERVER_TEST_DIR / "blacklist.txt"
    blacklist_file.write_text("localhost.evilcorp.com")

    # target-filtering before creating a target should fail
    process = subprocess.run(
        BBCTL_COMMAND + ["asset", "list", "--target", "test-target", "--json"], capture_output=True, text=True
    )
    assert process.returncode == 1
    assert process.stderr.endswith("[ERROR] Target not found.\n")

    # create a target
    process = subprocess.run(
        BBCTL_COMMAND
        + [
            "scan",
            "target",
            "create",
            "--name",
            "test-target",
            "--seeds",
            str(target_file),
            "--blacklist",
            str(blacklist_file),
        ],
        capture_output=True,
        text=True,
    )
    assert "Target created successfully" in process.stderr
    target = orjson.loads(process.stdout)

    # wait for assets to be tagged with new target
    sleep(1)

    # by target name
    process1 = subprocess.run(
        BBCTL_COMMAND + ["asset", "list", "--target", "test-target", "--json"], capture_output=True, text=True
    )
    # by target ID
    process2 = subprocess.run(
        BBCTL_COMMAND + ["asset", "list", "--target", target["id"], "--json"], capture_output=True, text=True
    )
    # by default
    process3 = subprocess.run(
        BBCTL_COMMAND + ["asset", "list", "--json", "--in-scope-only"], capture_output=True, text=True
    )
    proc1_output = [orjson.loads(line) for line in process1.stdout.splitlines()]
    proc2_output = [orjson.loads(line) for line in process2.stdout.splitlines()]
    proc3_output = [orjson.loads(line) for line in process3.stdout.splitlines()]
    proc1_hosts = {a["host"] for a in proc1_output}
    proc2_hosts = {a["host"] for a in proc2_output}
    proc3_hosts = {a["host"] for a in proc3_output}
    assert proc1_hosts == {
        "127.0.0.1",
        "127.0.0.2",
        "evilcorp.com",
        "www2.evilcorp.com",
        "api.evilcorp.com",
        "cname.evilcorp.com",
        "www.evilcorp.com",
        "t1.tech.evilcorp.com",
        "t2.tech.evilcorp.com",
        "evilcorp.azure.com",  # this one resolves to 127.0.0.3 so it matches
        # localhost.evilcorp.com is blacklisted
    }
    assert proc1_hosts == proc2_hosts
    assert proc1_hosts == proc3_hosts
