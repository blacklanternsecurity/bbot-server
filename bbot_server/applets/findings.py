from fastapi import Query
from typing import Annotated, Optional

from bbot_server.applets._base import BaseApplet, api_endpoint
from bbot_server.assets.custom_fields import CustomAssetFields
from bbot_server.models.finding_models import Finding, SEVERITY_COLORS, SeverityScore


# add 'findings' field to the main asset model
class FindingFields(CustomAssetFields):
    findings: Annotated[list[str], "indexed", "indexed-text"] = []
    finding_severities: Annotated[dict[str, int], "indexed"] = {}
    finding_max_severity: Optional[Annotated[str, "indexed"]] = None
    finding_max_severity_score: Annotated[int, "indexed"] = 0


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
        async for finding in self.parent._get_assets(
            type="Finding", domain=domain, target_id=target_id, fields=["name"]
        ):
            finding_name = finding["name"]
            findings[finding_name] = findings.get(finding_name, 0) + 1
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
        async for finding in self.parent._get_assets(
            type="Finding", domain=domain, target_id=target_id, fields=["severity"]
        ):
            severity = finding.get("severity", "INFO")
            findings[severity] = findings.get(severity, 0) + 1
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
        # update finding names
        findings = set(getattr(asset, "findings", []))
        findings.add(finding.name)
        asset.findings = sorted(findings)
        return await self._insert_or_update_finding(finding, asset, event)

    async def compute_stats(self, asset, stats):
        """
        Compute stats based on:
            - finding names
            - finding severities
            - finding hosts
            - finding max severity
            - finding max severity score
        """
        finding_names = getattr(asset, "findings", [])
        finding_severities = getattr(asset, "finding_severities", {})
        finding_stats = stats.get("findings", {})
        name_stats = finding_stats.get("names", {})
        counts_by_host = finding_stats.get("counts_by_host", {})
        severities_by_host = finding_stats.get("severities_by_host", {})
        severity_stats = finding_stats.get("severities", {})

        for finding_name in finding_names:
            name_stats[finding_name] = name_stats.get(finding_name, 0) + 1
            counts_by_host[asset.host] = counts_by_host.get(asset.host, 0) + 1
        for finding_severity, count in finding_severities.items():
            severity_stats[finding_severity] = severity_stats.get(finding_severity, 0) + count

        max_severity_score = max([asset.finding_max_severity_score, finding_stats.get("max_severity_score", 0)])
        finding_stats["max_severity_score"] = max_severity_score
        if max_severity_score > 0:
            max_severity = SeverityScore.to_severity(max_severity_score)
        else:
            max_severity = None
        finding_stats["max_severity"] = max_severity

        if asset.finding_max_severity_score > 0:
            severities_by_host[asset.host] = {
                "max_severity": asset.finding_max_severity,
                "max_severity_score": asset.finding_max_severity_score,
            }

        finding_stats["names"] = dict(sorted(name_stats.items(), key=lambda x: x[1], reverse=True))
        finding_stats["counts_by_host"] = dict(sorted(counts_by_host.items(), key=lambda x: x[1], reverse=True))
        finding_stats["severities_by_host"] = dict(
            sorted(severities_by_host.items(), key=lambda x: x[1]["max_severity_score"], reverse=True)
        )
        finding_stats["severities"] = dict(sorted(severity_stats.items(), key=lambda x: x[1], reverse=True))
        stats["findings"] = finding_stats

        return stats

    async def _insert_or_update_finding(self, finding: Finding, asset, event=None):
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

        # update the asset
        finding_severities = getattr(asset, "finding_severities", {})
        finding_severities[finding.severity] = finding_severities.get(finding.severity, 0) + 1
        asset.finding_severities = dict(sorted(finding_severities.items(), key=lambda x: x[1], reverse=True))
        severity_scores = {SeverityScore.to_score(severity) for severity in finding_severities}
        if severity_scores:
            asset.finding_max_severity_score = max(severity_scores)
            asset.finding_max_severity = SeverityScore.to_severity(asset.finding_max_severity_score)
        else:
            asset.finding_max_severity_score = 0
            asset.finding_max_severity = None

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
