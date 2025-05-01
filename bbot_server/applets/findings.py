from fastapi import Query
from typing import Annotated

from bbot_server.applets._base import BaseApplet, api_endpoint
from bbot_server.assets.custom_fields import CustomAssetFields
from bbot_server.models.finding_models import Finding, SEVERITY_COLORS


# add 'findings' field to the main asset model
class FindingFields(CustomAssetFields):
    findings: Annotated[list[str], "indexed", "indexed-text"] = []


class FindingsApplet(BaseApplet):
    name = "Findings"
    watched_events = ["VULNERABILITY", "FINDING"]
    description = "vulnerabilities discovered during scans"
    model = Finding

    @api_endpoint(
        "/get",
        methods=["GET"],
        summary="Get a single finding by its ID",
    )
    async def get_finding(self, id: str) -> Finding:
        finding = await self.root._get_asset(type="Finding", query={"id": id})
        if not finding:
            raise self.BBOTServerNotFoundError("Finding not found")
        return Finding(**finding)

    @api_endpoint(
        "/list",
        methods=["GET"],
        type="http_stream",
        response_model=Finding,
        summary="Search and filter findings by domain, target, severity, etc.",
    )
    async def get_findings(
        self,
        search: Annotated[str, Query(description="search finding name or description")] = None,
        domain: Annotated[str, Query(description="domain or subdomain")] = None,
        target_id: Annotated[str, Query(description="target name or id")] = None,
        min_severity: Annotated[int, Query(description="minimum severity (1=INFO, 5=CRITICAL)", ge=1, le=5)] = 1,
        max_severity: Annotated[int, Query(description="maximum severity (1=INFO, 5=CRITICAL)", ge=1, le=5)] = 5,
    ):
        if min_severity > max_severity:
            raise self.BBOTServerValueError("min_severity must be less than or equal to max_severity")

        async for finding in self.root._get_assets(
            type="Finding",
            domain=domain,
            target_id=target_id,
            query={
                "severity_score": {
                    "$gte": min_severity,
                    "$lte": max_severity,
                },
            },
            search=search,
            sort=[("severity_score", -1)],
        ):
            yield Finding(**finding)

    @api_endpoint(
        "/stats_by_name",
        methods=["GET"],
        summary="Return a high-level count of findings by name",
        mcp=True,
    )
    async def finding_counts(
        self,
        domain: Annotated[str, Query(description="domain or subdomain")] = None,
        target_id: Annotated[str, Query(description="target name or id")] = None,
        min_severity: Annotated[int, Query(description="minimum severity (1=INFO, 5=CRITICAL)", ge=1, le=5)] = 1,
        max_severity: Annotated[int, Query(description="maximum severity (1=INFO, 5=CRITICAL)", ge=1, le=5)] = 5,
    ) -> dict[str, int]:
        findings = {}
        async for asset in self.parent._get_assets(
            type="Finding", domain=domain, target_id=target_id, fields=["name"]
        ):
            finding_name = asset["name"]
            try:
                findings[finding_name] += 1
            except KeyError:
                findings[finding_name] = 1
        findings = dict(sorted(findings.items(), key=lambda x: x[1], reverse=True))
        return findings

    @api_endpoint(
        "/stats_by_severity",
        methods=["GET"],
        summary="Return a high-level count of findings by severity",
        mcp=True,
    )
    async def severity_counts(
        self,
        domain: Annotated[str, Query(description="domain or subdomain")] = None,
        target_id: Annotated[str, Query(description="target name or id")] = None,
        min_severity: Annotated[int, Query(description="minimum severity (1=INFO, 5=CRITICAL)", ge=1, le=5)] = 1,
        max_severity: Annotated[int, Query(description="maximum severity (1=INFO, 5=CRITICAL)", ge=1, le=5)] = 5,
    ) -> dict[str, int]:
        findings = {}
        async for asset in self.parent._get_assets(
            type="Finding", domain=domain, target_id=target_id, fields=["severity"]
        ):
            severity = asset.get("severity", "INFO")
            try:
                findings[severity] += 1
            except KeyError:
                findings[severity] = 1
        findings = dict(sorted(findings.items(), key=lambda x: x[1], reverse=True))
        return findings

    async def handle_event(self, event, asset):
        name = event.data_json["name"]
        description = event.data_json["description"]
        confidence = event.data_json.get("confidence", 1)
        severity = event.data_json.get("severity", "INFO")
        cves = event.data_json.get("cves", [])
        finding = Finding(
            name=name,
            host=asset.host,
            description=description,
            confidence=confidence,
            severity=severity,
            cves=cves,
            event=event,
        )
        findings = set(getattr(asset, "findings", []))
        findings.add(finding.name)
        asset.findings = sorted(findings)
        return await self._insert_or_update_finding(finding, event)

    def compute_stats(self, asset, stats):
        vulns = getattr(asset, "findings", [])
        vuln_stats = stats.get("findings", {})
        for v in vulns:
            try:
                vuln_stats[v] += 1
            except KeyError:
                vuln_stats[v] = 1
        stats["vulnerabilities"] = vuln_stats
        return stats

    async def _insert_or_update_finding(self, finding: Finding, event=None):
        """
        Insert a new finding into the database, or update an existing one.

        Returns a list of activities. If the finding was new, a NEW_FINDING activity will be returned.
        """
        query = {
            "id": finding.id,
        }
        existing_finding = await self.root._get_asset(
            query=query,
            fields=["created"],
        )
        if existing_finding:
            finding.created = existing_finding["created"]
            # update the modified field
            await self.collection.update_one(
                query,
                {
                    "$set": {
                        "modified": self.helpers.utc_now(),
                        "confidence": finding.confidence,
                        "severity": finding.severity,
                    }
                },
            )
            return []

        # insert the new vulnerability
        await self.collection.insert_one(finding.model_dump())

        severity_color = SEVERITY_COLORS[finding.severity_score]

        return [
            self.make_activity(
                type="NEW_FINDING",
                description=f"New finding (severity {finding.severity}): [[bold {severity_color}]{finding.name}[/bold {severity_color}]] on [bold]{finding.host}[/bold]",
                event=event,
                detail=finding.model_dump(),
            )
        ]
