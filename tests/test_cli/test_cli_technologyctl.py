import orjson
import subprocess
from time import sleep

from bbot_server.modules.targets.targets_models import Target

from bbot_server.modules.technologies.technology_models import Technology
from tests.conftest import BBCTL_COMMAND, INGEST_PROCESSING_DELAY, BBOT_SERVER_TEST_DIR


def test_cli_technologyctl(bbot_server_http, bbot_watchdog, bbot_out_file):
    # we shouldn't have any technologies yet
    command = BBCTL_COMMAND + ["technology", "list", "--json"]
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
    sleep(INGEST_PROCESSING_DELAY * 2)

    # list technologies (JSON)
    command = BBCTL_COMMAND + ["technology", "list", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert len(process.stdout.splitlines()) == 4
    technologies = [Technology(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert len(technologies) == 4
    assert {(t.netloc, t.technology) for t in technologies} == {
        ("t1.tech.evilcorp.com:80", "cpe:/a:apache:http_server:2.4.12"),
        ("t1.tech.evilcorp.com:443", "cpe:/a:apache:http_server:2.4.12"),
        ("t2.tech.evilcorp.com:443", "cpe:/a:apache:http_server:2.4.12"),
        ("t2.tech.evilcorp.com:443", "cpe:/a:microsoft:internet_information_services"),
    }

    # list technologies by domain (JSON)
    command = BBCTL_COMMAND + ["technology", "list", "--domain", "evilcorp.net", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    technologies = [Technology(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert technologies == []
    command = BBCTL_COMMAND + ["technology", "list", "--domain", "evilcorp.com", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert len(process.stdout.splitlines()) == 4
    technologies = [Technology(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert len(technologies) == 4
    assert {(t.technology, t.netloc) for t in technologies} == {
        ("cpe:/a:apache:http_server:2.4.12", "t1.tech.evilcorp.com:80"),
        ("cpe:/a:apache:http_server:2.4.12", "t1.tech.evilcorp.com:443"),
        ("cpe:/a:apache:http_server:2.4.12", "t2.tech.evilcorp.com:443"),
        ("cpe:/a:microsoft:internet_information_services", "t2.tech.evilcorp.com:443"),
    }

    # list technologies by host (JSON)
    command = BBCTL_COMMAND + ["technology", "list", "--host", "t1.tech.evilcorp.com", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert len(process.stdout.splitlines()) == 2
    technologies = [Technology(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert len(technologies) == 2
    assert {(t.technology, t.netloc) for t in technologies} == {
        ("cpe:/a:apache:http_server:2.4.12", "t1.tech.evilcorp.com:80"),
        ("cpe:/a:apache:http_server:2.4.12", "t1.tech.evilcorp.com:443"),
    }

    # list technologies (text)
    command = BBCTL_COMMAND + ["technology", "list"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert process.stdout.count("cpe:/a:apache") == 3
    assert process.stdout.count("cpe:/a:microsoft") == 1
    assert "t1.tech.evil" in process.stdout
    assert "t2.tech.evil" in process.stdout

    # search technologies (JSON)
    command = BBCTL_COMMAND + ["technology", "list", "--search", "apache", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert len(process.stdout.splitlines()) == 3
    technologies = [Technology(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert len(technologies) == 3
    assert {(t.netloc, t.technology) for t in technologies} == {
        ("t1.tech.evilcorp.com:80", "cpe:/a:apache:http_server:2.4.12"),
        ("t1.tech.evilcorp.com:443", "cpe:/a:apache:http_server:2.4.12"),
        ("t2.tech.evilcorp.com:443", "cpe:/a:apache:http_server:2.4.12"),
    }

    # search technologies (text)
    command = BBCTL_COMMAND + ["technology", "list", "--search", "apache"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    # should only match apache and not IIS
    assert process.stdout.count("cpe:/a:apache") == 3
    assert not "internet" in process.stdout

    command = BBCTL_COMMAND + ["technology", "list", "--search", "microsoft"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert process.stdout.count("cpe:/a:microsoft") == 1
    assert not "apache" in process.stdout

    # filter technologies by domain
    command = BBCTL_COMMAND + ["technology", "list", "--domain", "evilcorp.com", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    technologies = [Technology(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert len(technologies) == 4
    assert {(t.netloc, t.technology) for t in technologies} == {
        ("t1.tech.evilcorp.com:80", "cpe:/a:apache:http_server:2.4.12"),
        ("t1.tech.evilcorp.com:443", "cpe:/a:apache:http_server:2.4.12"),
        ("t2.tech.evilcorp.com:443", "cpe:/a:apache:http_server:2.4.12"),
        ("t2.tech.evilcorp.com:443", "cpe:/a:microsoft:internet_information_services"),
    }
    command = BBCTL_COMMAND + ["technology", "list", "--domain", "tech.evilcorp.com", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    technologies = [Technology(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert len(technologies) == 4
    assert {(t.netloc, t.technology) for t in technologies} == {
        ("t1.tech.evilcorp.com:80", "cpe:/a:apache:http_server:2.4.12"),
        ("t1.tech.evilcorp.com:443", "cpe:/a:apache:http_server:2.4.12"),
        ("t2.tech.evilcorp.com:443", "cpe:/a:apache:http_server:2.4.12"),
        ("t2.tech.evilcorp.com:443", "cpe:/a:microsoft:internet_information_services"),
    }
    command = BBCTL_COMMAND + ["technology", "list", "--domain", "t1.tech.evilcorp.com", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    technologies = [Technology(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert len(technologies) == 2
    assert {(t.netloc, t.technology) for t in technologies} == {
        ("t1.tech.evilcorp.com:80", "cpe:/a:apache:http_server:2.4.12"),
        ("t1.tech.evilcorp.com:443", "cpe:/a:apache:http_server:2.4.12"),
    }
    command = BBCTL_COMMAND + ["technology", "list", "--domain", "asdf.tech.evilcorp.com", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert process.stdout == ""

    # filter technologies by target id
    # create a new target that matches two technologies
    target_file = BBOT_SERVER_TEST_DIR / "targets"
    target_file.write_text("t2.tech.evilcorp.com")
    command = BBCTL_COMMAND + ["scan", "target", "create", "--target", target_file, "--name", "evilcorp1"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0

    # wait for the target to be processed
    for _ in range(60):
        command = BBCTL_COMMAND + ["scan", "target", "list", "--json"]
        process = subprocess.run(command, capture_output=True, text=True)
        assert process.returncode == 0
        targets = [Target(**orjson.loads(line)) for line in process.stdout.splitlines()]
        if len(targets) == 1:
            break
        sleep(0.5)
    else:
        assert False, "Target not created successfully"

    # list technologies for the target (JSON)
    for _ in range(60):
        command = BBCTL_COMMAND + ["technology", "list", "--target", "evilcorp1", "--json"]
        process = subprocess.run(command, capture_output=True, text=True)
        assert process.returncode == 0
        technologies = [Technology(**orjson.loads(line)) for line in process.stdout.splitlines()]
        if len(technologies) == 2 and {(t.netloc, t.technology) for t in technologies} == {
            ("t2.tech.evilcorp.com:443", "cpe:/a:apache:http_server:2.4.12"),
            ("t2.tech.evilcorp.com:443", "cpe:/a:microsoft:internet_information_services"),
        }:
            break
        sleep(0.5)
    else:
        assert False, "Technologies not found for target"

    # list technologies for the target (text)
    for _ in range(60):
        command = BBCTL_COMMAND + ["technology", "list", "--target", "evilcorp1"]
        process = subprocess.run(command, capture_output=True, text=True)
        if (
            process.returncode == 0
            and process.stdout.count("cpe:/a:apache") == 1
            and process.stdout.count("cpe:/a:microsoft") == 1
        ):
            break
        sleep(0.5)
    else:
        assert False, "Technologies not found for target"

    # summarize technologies (JSON)
    command = BBCTL_COMMAND + ["technology", "summarize", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    summary = [orjson.loads(line) for line in process.stdout.splitlines()]
    assert len(summary) == 2
    apache_summary = [t for t in summary if t["technology"] == "cpe:/a:apache:http_server:2.4.12"]
    assert len(apache_summary) == 1
    assert apache_summary[0]["hosts"] == ["t1.tech.evilcorp.com", "t2.tech.evilcorp.com"]
    microsoft_summary = [t for t in summary if t["technology"] == "cpe:/a:microsoft:internet_information_services"]
    assert len(microsoft_summary) == 1
    assert microsoft_summary[0]["hosts"] == ["t2.tech.evilcorp.com"]

    # summarize technologies (text)
    command = BBCTL_COMMAND + ["technology", "summarize"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert process.stdout.count("cpe:/a:apache") == 1
    assert process.stdout.count("cpe:/a:microsoft") == 1
    assert "t1.tech.evil" in process.stdout
    assert "t2.tech.evil" in process.stdout
