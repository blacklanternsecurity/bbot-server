import orjson
import subprocess
from time import sleep

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

    # # TODO: list technologies by target (JSON)
    # seeds_file = BBOT_SERVER_TEST_DIR / "seeds.txt"
    # seeds_file.unlink(missing_ok=True)
    # seeds_file.write_text("tech2.evilcorp.com")
    # process = subprocess.run(
    #     BBCTL_COMMAND + ["--no-color", "scan", "target", "create", "--seeds", str(seeds_file)],
    #     capture_output=True,
    #     text=True,
    # )
    # assert process.returncode == 0
    # assert "Target created successfully" in process.stderr
    # target = orjson.loads(process.stdout)
    # assert target["name"] == "Target 1"
    # assert set(target["seeds"]) == {"t2.tech.evilcorp.com"}
    # # give some time for target to be processed
    # sleep(2)

    # command = BBCTL_COMMAND + ["technology", "list", "--target", "Target 1", "--json"]
    # process = subprocess.run(command, capture_output=True, text=True)
    # assert process.returncode == 0
    # assert len(process.stdout.splitlines()) == 2
    # technologies = [Technology(**orjson.loads(line)) for line in process.stdout.splitlines()]
    # assert len(technologies) == 2
    # assert {(t.technology, t.netloc) for t in technologies} == {
    #     ("cpe:/a:apache:http_server:2.4.12", "t2.tech.evilcorp.com:443"),
    #     ("cpe:/a:microsoft:internet_information_services", "t2.tech.evilcorp.com:443"),
    # }

    # list technologies (text)
    command = BBCTL_COMMAND + ["technology", "list"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert process.stdout.count("cpe:/a:apache") == 1
    assert process.stdout.count("cpe:/a:microsoft") == 1
    assert "t1.tech.evil" in process.stdout

    # search technologies (JSON)
    command = BBCTL_COMMAND + ["technology", "search", "apache", "--json"]
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
    command = BBCTL_COMMAND + ["technology", "search", "apache"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    # should only match apache and not IIS
    assert process.stdout.count("cpe:/a:apache") == 3
    assert not "internet" in process.stdout

    command = BBCTL_COMMAND + ["technology", "search", "microsoft"]
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

    # # TODO: filter technologies by target id
    # target_file = BBOT_SERVER_TEST_DIR / "targets"
    # target_file.write_text("t2.tech.evilcorp.com")
    # command = BBCTL_COMMAND + ["scan", "target", "create", "--seeds", target_file, "--name", "evilcorp1"]
    # process = subprocess.run(command, capture_output=True, text=True)
    # assert process.returncode == 0

    # # wait for a sec for the target to be processed
    # sleep(1)
    # command = BBCTL_COMMAND + ["technology", "list", "--target", "evilcorp1", "--json"]
    # process = subprocess.run(command, capture_output=True, text=True)
    # assert process.returncode == 0
    # technologies = [Technology(**orjson.loads(line)) for line in process.stdout.splitlines()]
    # assert len(technologies) == 2
    # assert {(t.netloc, t.technology) for t in technologies} == {
    #     ("t2.tech.evilcorp.com:443", "cpe:/a:apache:http_server:2.4.12"),
    #     ("t2.tech.evilcorp.com:443", "cpe:/a:microsoft:internet_information_services"),
    # }
