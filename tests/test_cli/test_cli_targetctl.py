import orjson
import subprocess

from bbot_server.modules.targets.targets_models import Target
from tests.conftest import BBCTL_COMMAND, BBOT_SERVER_TEST_DIR


def test_cli_targetctl(bbot_server_http):
    # we shouldn't have any targets yet
    command = BBCTL_COMMAND + ["scan", "target", "list", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert process.stdout == ""

    # create a target (nonexistent file should fail)
    seeds_file = BBOT_SERVER_TEST_DIR / "seeds.txt"
    seeds_file.unlink(missing_ok=True)
    process = subprocess.run(
        BBCTL_COMMAND + ["--no-color", "scan", "target", "create", "--seeds", str(seeds_file)],
        capture_output=True,
        text=True,
    )
    assert process.returncode == 1
    assert f"Unable to find seeds at {seeds_file}" in process.stderr

    # create a target
    seeds_file.write_text("evilcorp.com\nevilcorp.net")
    process = subprocess.run(
        BBCTL_COMMAND + ["--no-color", "scan", "target", "create", "--seeds", str(seeds_file)],
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0
    assert "Target created successfully" in process.stderr
    target = orjson.loads(process.stdout)
    assert target["name"] == "Target 1"
    assert set(target["seeds"]) == {"evilcorp.com", "evilcorp.net"}

    # creating the same target again should fail
    process = subprocess.run(
        BBCTL_COMMAND + ["--no-color", "scan", "target", "create", "--seeds", str(seeds_file)],
        capture_output=True,
        text=True,
    )
    assert process.returncode == 1
    assert "Identical target already exists" in process.stderr

    # create a second target
    seeds_file.write_text("evilcorp.org")
    process = subprocess.run(
        BBCTL_COMMAND + ["--no-color", "scan", "target", "create", "--seeds", str(seeds_file), "--strict-scope"],
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0
    assert "Target created successfully" in process.stderr
    assert process.returncode == 0
    target2 = orjson.loads(process.stdout)
    assert target2["name"] == "Target 2"
    assert set(target2["seeds"]) == {"evilcorp.org"}

    seeds_file.unlink()

    # list targets (json)
    process = subprocess.run(BBCTL_COMMAND + ["scan", "target", "list", "--json"], capture_output=True, text=True)
    assert process.returncode == 0
    targets = [Target(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert len(targets) == 2
    targets = {t.name: t for t in targets}
    assert set(targets["Target 1"].seeds) == {"evilcorp.com", "evilcorp.net"}
    assert set(targets["Target 2"].seeds) == {"evilcorp.org"}
    assert targets["Target 1"].strict_dns_scope is False
    assert targets["Target 2"].strict_dns_scope is True

    # list targets (csv)
    process = subprocess.run(BBCTL_COMMAND + ["scan", "target", "list", "--csv"], capture_output=True, text=True)
    assert process.returncode == 0
    lines = process.stdout.splitlines()
    assert len(lines) == 3
    assert lines[0] == "name,description,seeds,whitelist,blacklist,strict_scope,created,modified"
    assert lines[1].startswith("Target 1,,2,0,0,No,")
    assert lines[2].startswith("Target 2,,1,0,0,Yes,")

    # list targets (text)
    process = subprocess.run(BBCTL_COMMAND + ["scan", "target", "list"], capture_output=True, text=True)
    assert process.returncode == 0
    assert process.stdout.count("Target") == 2

    # delete target1 (must specify name or id)
    process = subprocess.run(
        BBCTL_COMMAND
        + [
            "scan",
            "target",
            "delete",
        ],
        capture_output=True,
        text=True,
    )
    # TODO: why does this puke only on github actions?
    assert "Missing argument" in process.stderr or "positional argument" in process.stderr
    assert process.returncode in (1, 2)

    # delete the target (by name)
    process = subprocess.run(
        BBCTL_COMMAND + ["scan", "target", "delete", "Target 1"],
        capture_output=True,
        text=True,
    )
    assert "Target deleted successfully" in process.stderr
    assert process.returncode == 0

    # make sure target1 is gone
    process = subprocess.run(BBCTL_COMMAND + ["scan", "target", "list", "--json"], capture_output=True, text=True)
    assert process.returncode == 0
    targets = [Target(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert len(targets) == 1
    assert targets[0].name == "Target 2"

    # delete nonexistent target
    process = subprocess.run(
        BBCTL_COMMAND + ["scan", "target", "delete", "Target 1"],
        capture_output=True,
        text=True,
    )
    assert process.returncode == 1
    assert "Target not found" in process.stderr
