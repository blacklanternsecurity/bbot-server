import orjson
import subprocess
from time import sleep

from tests.conftest import BBCTL_COMMAND, INGEST_PROCESSING_DELAY, BBOT_SERVER_TEST_DIR
from bbot_server.modules.findings.findings_models import Finding


def test_cli_findingctl(bbot_server_http, bbot_watchdog, bbot_out_file):
    # we shouldn't have any findings yet
    command = BBCTL_COMMAND + ["finding", "list", "--json"]
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

    # list findings (JSON)
    command = BBCTL_COMMAND + ["finding", "list", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert len(process.stdout.splitlines()) == 4
    findings = [Finding(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert len(findings) == 4
    assert {f.name for f in findings} == {"CVE-2024-12345", "CVE-2025-54321"}
    assert {f.host for f in findings} == {"www.evilcorp.com", "www2.evilcorp.com", "api.evilcorp.com"}
    assert {f.severity for f in findings} == {"HIGH", "CRITICAL"}
    assert {f.severity_score for f in findings} == {4, 5}
    assert {f.confidence for f in findings} == {1}
    assert {f.url for f in findings} == {
        "http://www.evilcorp.com/",
        "http://www2.evilcorp.com/",
        "https://api.evilcorp.com/",
    }
    assert {f.netloc for f in findings} == {
        "www.evilcorp.com:80",
        "www2.evilcorp.com:80",
        "api.evilcorp.com:443",
    }

    # list findings (text)
    command = BBCTL_COMMAND + ["finding", "list"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert process.stdout.count("CVE-2024") == 2
    assert process.stdout.count("CVE-2025") == 2

    # search findings (JSON)
    command = BBCTL_COMMAND + ["finding", "list", "--search", "whippin", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert len(process.stdout.splitlines()) == 2
    findings = [Finding(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert len(findings) == 2
    assert {f.name for f in findings} == {"CVE-2025-54321"}
    assert {f.host for f in findings} == {"www2.evilcorp.com", "api.evilcorp.com"}

    # filter findings by host (JSON)
    command = BBCTL_COMMAND + ["finding", "list", "--host", "www2.evilcorp.com", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert len(process.stdout.splitlines()) == 2
    findings = [Finding(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert len(findings) == 2
    assert {f.name for f in findings} == {"CVE-2024-12345", "CVE-2025-54321"}
    assert {f.host for f in findings} == {"www2.evilcorp.com"}

    # invalid severity
    command = BBCTL_COMMAND + ["finding", "list", "--min-severity", "ASDF", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 1
    assert "Invalid severity" in process.stderr

    # filter findings by domain (JSON)
    command = BBCTL_COMMAND + ["finding", "list", "--domain", "evilcorp.com", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert len(process.stdout.splitlines()) == 4
    findings = [Finding(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert len(findings) == 4
    assert {f.name for f in findings} == {"CVE-2024-12345", "CVE-2025-54321"}
    assert {f.host for f in findings} == {"www.evilcorp.com", "www2.evilcorp.com", "api.evilcorp.com"}

    command = BBCTL_COMMAND + ["finding", "list", "--domain", "www2.evilcorp.com", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert len(process.stdout.splitlines()) == 2
    findings = [Finding(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert len(findings) == 2
    assert {f.name for f in findings} == {"CVE-2024-12345", "CVE-2025-54321"}
    assert {f.host for f in findings} == {"www2.evilcorp.com"}

    # filter findings by target (JSON)
    # create target
    target_file = BBOT_SERVER_TEST_DIR / "targets"
    target_file.write_text("www2.evilcorp.com")
    command = BBCTL_COMMAND + ["scan", "target", "create", "--seeds", target_file, "--name", "evilcorp1"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0

    command = BBCTL_COMMAND + ["finding", "list", "--target", "evilcorp1", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert len(process.stdout.splitlines()) == 2
    findings = [Finding(**orjson.loads(line)) for line in process.stdout.splitlines()]
    assert len(findings) == 2
    assert {f.name for f in findings} == {"CVE-2024-12345", "CVE-2025-54321"}
    assert {f.host for f in findings} == {"www2.evilcorp.com"}
