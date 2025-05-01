from hashlib import sha1
from tests.test_applets.base import BaseAppletTest


class TestAppletFindings(BaseAppletTest):
    needs_watchdog = True

    async def setup(self):
        # at the beginning, everything should be empty
        assert [f async for f in self.bbot_server.get_findings()] == []

    async def after_scan_1(self):
        # we should have 2 findings
        findings = [f async for f in self.bbot_server.get_findings()]
        assert len(findings) == 2
        assert {f.name for f in findings} == {"CVE-2024-12345"}
        assert {f.host for f in findings} == {"www.evilcorp.com", "www2.evilcorp.com"}
        assert {f.severity for f in findings} == {"HIGH"}
        assert {f.severity_score for f in findings} == {4}
        assert {f.confidence for f in findings} == {1}

    async def after_scan_2(self):
        findings = [f async for f in self.bbot_server.get_findings()]
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

        asset = await self.bbot_server.get_asset(host="www2.evilcorp.com")
        assert asset.findings == ["CVE-2024-12345", "CVE-2025-54321"]

        # stats by finding name
        finding_counts = await self.bbot_server.finding_counts()
        assert finding_counts == {"CVE-2024-12345": 2, "CVE-2025-54321": 2}

        # stats by severity
        severity_counts = await self.bbot_server.severity_counts()
        assert severity_counts == {"HIGH": 2, "CRITICAL": 2}

        # id should be a hash of the description and netloc
        finding_id = sha1(f"That's a whippin':api.evilcorp.com:443".encode()).hexdigest()
        finding_by_id = await self.bbot_server.get_finding(id=finding_id)
        assert finding_by_id.name == "CVE-2025-54321"
        assert finding_by_id.host == "api.evilcorp.com"
        assert finding_by_id.severity == "CRITICAL"
        assert finding_by_id.severity_score == 5
        assert finding_by_id.confidence == 1
        assert finding_by_id.url == "https://api.evilcorp.com/"

        # search for a string in the description
        findings = [f async for f in self.bbot_server.get_findings(search="whippin")]
        assert len(findings) == 2
        assert {f.name for f in findings} == {"CVE-2025-54321"}
        assert {f.host for f in findings} == {"www2.evilcorp.com", "api.evilcorp.com"}
        findings = [f async for f in self.bbot_server.get_findings(search="paddlin")]
        assert len(findings) == 2
        assert {f.name for f in findings} == {"CVE-2024-12345"}
        assert {f.host for f in findings} == {"www.evilcorp.com", "www2.evilcorp.com"}
