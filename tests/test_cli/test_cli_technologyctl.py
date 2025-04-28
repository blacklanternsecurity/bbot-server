import orjson
import subprocess
from time import sleep

from tests.conftest import BBCTL_COMMAND
from bbot_server.models.technology_models import Technology


def test_cli_technologyctl(bbot_server_http, bbot_watchdog, bbot_out_file):
    # we shouldn't have any technologies yet
    command = BBCTL_COMMAND + ["asset", "technology", "list", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert process.stdout == ""

    scan1_out_file, scan2_out_file = bbot_out_file

    # ingest the scan data
    subprocess.run(
        BBCTL_COMMAND + ["event", "ingest"],
        input=scan1_out_file + "\n" + scan2_out_file,
        capture_output=True,
        text=True,
    )

    # wait for events to be processed
    sleep(1)

    # list technologies (JSON)
    command = BBCTL_COMMAND + ["asset", "technology", "list", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert len(process.stdout.splitlines()) == 4
    technologies = [Technology(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert len(technologies) == 4
    assert {(t.technology, t.netloc) for t in technologies} == {
        ("cpe:/a:apache:http_server:2.4.12", "tech1.evilcorp.com:80"),
        ("cpe:/a:apache:http_server:2.4.12", "tech1.evilcorp.com:443"),
        ("cpe:/a:apache:http_server:2.4.12", "tech2.evilcorp.com:443"),
        ("cpe:/a:microsoft:internet_information_services", "tech2.evilcorp.com:443"),
    }

    # list technologies (text)
    command = BBCTL_COMMAND + ["asset", "technology", "list"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert process.stdout.count("cpe:/a:apache") == 1
    assert process.stdout.count("cpe:/a:microsoft") == 1
    assert "tech1.evil" in process.stdout

    # search technologies (JSON)
    command = BBCTL_COMMAND + ["asset", "technology", "search", "apache", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert len(process.stdout.splitlines()) == 3
    technologies = [Technology(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert len(technologies) == 3
    assert {(t.technology, t.netloc) for t in technologies} == {
        ("cpe:/a:apache:http_server:2.4.12", "tech1.evilcorp.com:80"),
        ("cpe:/a:apache:http_server:2.4.12", "tech1.evilcorp.com:443"),
        ("cpe:/a:apache:http_server:2.4.12", "tech2.evilcorp.com:443"),
    }

    # search technologies (text)
    command = BBCTL_COMMAND + ["asset", "technology", "search", "apache"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    # should only match apache and not IIS
    assert process.stdout.count("cpe:/a:apache") == 3
    assert not "internet" in process.stdout

    command = BBCTL_COMMAND + ["asset", "technology", "search", "microsoft"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert process.stdout.count("cpe:/a:microsoft") == 1
    assert not "apache" in process.stdout
