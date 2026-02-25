import pytest

pytestmark = pytest.mark.skip(reason="Requires events/watchdog modules shelved in Postgres migration")

import asyncio
from hashlib import sha1
from tests.test_applets.base import BaseAppletTest
from bbot_server.modules.targets.targets_models import CreateTarget


class TestAppletFindings(BaseAppletTest):
    needs_watchdog = True

    async def setup(self):
        # at the beginning, everything should be empty
        assert [f async for f in self.bbot_server.list_findings()] == []

        # create some targets
        target1 = CreateTarget(name="evilcorp1", target=["www2.evilcorp.com"])
        target2 = CreateTarget(name="evilcorp2", target=["www.evilcorp.com", "api.evilcorp.com"])
        self.target1 = await self.bbot_server.create_target(target1)
        self.target2 = await self.bbot_server.create_target(target2)

    async def after_scan_1(self):
        # we should have 2 findings
        findings = [f async for f in self.bbot_server.list_findings()]
        assert len(findings) == 2
        assert {f.name for f in findings} == {"CVE-2024-12345"}
        assert {f.host for f in findings} == {"www.evilcorp.com", "www2.evilcorp.com"}
        assert {f.severity for f in findings} == {"HIGH"}
        assert {f.severity_score for f in findings} == {4}
        assert {f.confidence for f in findings} == {"UNKNOWN"}
        assert {f.confidence_score for f in findings} == {1}

    async def after_scan_2(self):
        findings = [f async for f in self.bbot_server.list_findings()]
        assert len(findings) == 4
        assert {f.name for f in findings} == {"CVE-2024-12345", "CVE-2025-54321"}
        assert {f.host for f in findings} == {"www.evilcorp.com", "www2.evilcorp.com", "api.evilcorp.com"}
        assert {f.severity for f in findings} == {"HIGH", "CRITICAL"}
        assert {f.severity_score for f in findings} == {4, 5}
        assert {f.confidence for f in findings} == {"UNKNOWN"}
        assert {f.confidence_score for f in findings} == {1}
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
        assert finding_by_id.confidence == "UNKNOWN"
        assert finding_by_id.confidence_score == 1
        assert finding_by_id.url == "https://api.evilcorp.com/"
        assert finding_by_id.description == "That's a whippin'"

        # search for a string in the description
        findings = [f async for f in self.bbot_server.list_findings(search="whippin")]
        assert len(findings) == 2
        assert {f.name for f in findings} == {"CVE-2025-54321"}
        assert {f.host for f in findings} == {"www2.evilcorp.com", "api.evilcorp.com"}
        findings = [f async for f in self.bbot_server.list_findings(search="paddlin")]
        assert len(findings) == 2
        assert {f.name for f in findings} == {"CVE-2024-12345"}
        assert {f.host for f in findings} == {"www.evilcorp.com", "www2.evilcorp.com"}

        # activities
        activities = [a async for a in self.bbot_server.list_activities() if a.type == "NEW_FINDING"]
        www_activity = [a for a in activities if a.host == "www.evilcorp.com"][0]
        assert www_activity.description == "New finding with severity HIGH: [CVE-2024-12345] on www.evilcorp.com"
        assert (
            www_activity.description_colored
            == "New finding with severity [bold bright_red]HIGH[/bold bright_red]: [[bold bright_red]CVE-2024-12345[/bold bright_red]] on [bold]www.evilcorp.com[/bold]"
        )

        # filter findings by target
        findings1 = [f async for f in self.bbot_server.list_findings(target_id="evilcorp1")]
        assert len(findings1) == 2
        assert {f.name for f in findings1} == {"CVE-2024-12345", "CVE-2025-54321"}
        assert {f.host for f in findings1} == {"www2.evilcorp.com"}
        findings2 = [f async for f in self.bbot_server.list_findings(target_id="evilcorp2")]
        assert len(findings2) == 2
        assert {f.name for f in findings2} == {"CVE-2024-12345", "CVE-2025-54321"}
        assert {f.host for f in findings2} == {"www.evilcorp.com", "api.evilcorp.com"}

        # create a new target that matches one finding
        target = CreateTarget(name="evilcorp3", target=["www.evilcorp.com"])
        target = await self.bbot_server.create_target(target)
        # the finding should be automatically associated with the target
        for _ in range(60):
            findings = [f async for f in self.bbot_server.list_findings(target_id="evilcorp3")]
            if len(findings) == 1 and {f.name for f in findings} == {"CVE-2024-12345"}:
                break
            await asyncio.sleep(0.5)
        else:
            assert False, f"Findings for target3 are not ok. findings: {findings}"

        # filter findings by domain
        findings = [f async for f in self.bbot_server.list_findings(domain="evilcorp.com")]
        assert len(findings) == 4
        assert {f.name for f in findings} == {"CVE-2024-12345", "CVE-2025-54321"}
        assert {f.host for f in findings} == {"www.evilcorp.com", "www2.evilcorp.com", "api.evilcorp.com"}
        findings = [f async for f in self.bbot_server.list_findings(domain="www2.evilcorp.com")]
        assert len(findings) == 2
        assert {f.name for f in findings} == {"CVE-2024-12345", "CVE-2025-54321"}

        # filter findings by host
        findings = [f async for f in self.bbot_server.list_findings(host="www2.evilcorp.com")]
        assert len(findings) == 2
        assert {f.name for f in findings} == {"CVE-2024-12345", "CVE-2025-54321"}
        assert {f.host for f in findings} == {"www2.evilcorp.com"}
        findings = [f async for f in self.bbot_server.list_findings(host="evilcorp.com")]
        assert findings == []

        # filter findings by severity
        findings = [f async for f in self.bbot_server.list_findings(min_severity=4, max_severity=4)]
        assert len(findings) == 2
        assert {f.severity for f in findings} == {"HIGH"}
        findings = [f async for f in self.bbot_server.list_findings(min_severity=4, max_severity=5)]
        assert len(findings) == 4
        assert {f.severity for f in findings} == {"HIGH", "CRITICAL"}

        # advanced findings query
        query = {"name": {"$regex": "^CVE-2024-12"}}
        findings = [f async for f in self.bbot_server.query_findings(query=query)]
        assert len(findings) == 2
        assert all(f["name"] == "CVE-2024-12345" for f in findings)

        # findings aggregation
        aggregate_result = [
            f
            async for f in self.bbot_server.query_findings(
                aggregate=[{"$group": {"_id": "$name", "count": {"$sum": 1}}}, {"$sort": {"_id": 1}}]
            )
        ]
        assert aggregate_result == [{"_id": "CVE-2024-12345", "count": 2}, {"_id": "CVE-2025-54321", "count": 2}]

        # test count
        count = await self.bbot_server.count_findings(query={"name": "CVE-2024-12345"})
        assert count == 2
