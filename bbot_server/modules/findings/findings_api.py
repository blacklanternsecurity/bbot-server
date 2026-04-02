from fastapi import Query
from typing import Annotated, Optional

from bbot_server.assets import CustomAssetFields
from bbot_server.applets.base import BaseApplet, api_endpoint
from bbot_server.modules.findings.findings_models import Finding, SEVERITY_COLORS, SeverityScore, FindingsQuery

# Max CVSS score for each severity band (top of range).
# Used to derive a default risk score from finding_max_severity.
SEVERITY_TO_CVSS = {
    "INFO": 0.0,
    "LOW": 3.9,
    "MEDIUM": 6.9,
    "HIGH": 8.9,
    "CRITICAL": 10.0,
}


# add 'findings' field to the main asset model
class FindingFields(CustomAssetFields):
    findings: Annotated[list[str], "indexed", "indexed-text"] = []
    finding_severities: Annotated[dict[str, int], "indexed"] = {}
    finding_max_severity: Annotated[Optional[str], "indexed"] = None
    finding_max_severity_score: Annotated[int, "indexed"] = 0
    # Effective risk score for this asset: None or a float from 0.0 to 10.0
    # (1 decimal place). Auto-synced from finding_max_severity (using CVSS
    # thresholds) unless risk_override is True.
    risk: Annotated[Optional[float], "indexed"] = None
    # Whether risk has been manually overridden. When True, new findings
    # will NOT auto-update risk. Clearing the override resets this to False
    # and reverts risk to the CVSS-derived value.
    risk_override: Annotated[bool, "indexed"] = False


class FindingsApplet(BaseApplet):
    name = "Findings"
    watched_events = ["VULNERABILITY", "FINDING"]
    description = "vulnerabilities discovered during scans"
    attach_to = "assets"
    model = Finding

    @api_endpoint(
        "/get",
        methods=["GET"],
        summary="Get a single finding by its ID",
        mcp=True,
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
        summary="Simple, easily-curlable endpoint for listing findings, with basic filters",
        mcp=True,
    )
    async def list_findings(
        self,
        search: Annotated[str, Query(description="Search finding name or description")] = None,
        host: Annotated[str, Query(description="Filter by exact hostname or IP address")] = None,
        domain: Annotated[str, Query(description="Filter by domain or subdomain")] = None,
        target_id: Annotated[str, Query(description="Filter by target name or id")] = None,
        min_severity: Annotated[
            int, Query(description="Filter by minimum severity (1=INFO, 5=CRITICAL)", ge=1, le=5)
        ] = 1,
        max_severity: Annotated[
            int, Query(description="Filter by maximum severity (1=INFO, 5=CRITICAL)", ge=1, le=5)
        ] = 5,
    ):
        query = FindingsQuery(
            host=host,
            domain=domain,
            target_id=target_id,
            search=search,
            min_severity=min_severity,
            max_severity=max_severity,
            sort=[("severity_score", -1)],
        )
        async for finding in query.mongo_iter(self):
            yield Finding(**finding)

    @api_endpoint("/query", methods=["POST"], type="http_stream", response_model=dict, summary="Query findings")
    async def query_findings(self, query: FindingsQuery | None = None):
        """
        Advanced querying of findings. Choose your own filters and fields.
        """
        async for finding in query.mongo_iter(self):
            yield finding

    @api_endpoint("/count", methods=["POST"], summary="Count findings")
    async def count_findings(self, query: FindingsQuery | None = None) -> int:
        """
        Same as query_findings, except only returns the count
        """
        return await query.mongo_count(self)

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
        """
        Return a high-level count of findings by name
        """
        findings = {}
        query = FindingsQuery(
            domain=domain, target_id=target_id, min_severity=min_severity, max_severity=max_severity, fields=["name"]
        )
        async for finding in query.mongo_iter(self):
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
        query = FindingsQuery(
            domain=domain,
            target_id=target_id,
            min_severity=min_severity,
            max_severity=max_severity,
            fields=["severity"],
        )
        async for finding in query.mongo_iter(self):
            severity = finding["severity"]
            findings[severity] = findings.get(severity, 0) + 1
        findings = dict(sorted(findings.items(), key=lambda x: x[1], reverse=True))
        return findings

    @api_endpoint("/set_risk", methods=["PATCH"], summary="Set or clear a manual risk score for an asset")
    async def set_risk(
        self,
        host: Annotated[str, Query(description="The host of the asset to update")],
        risk: Annotated[
            Optional[float],
            Query(
                description=(
                    "Risk score from 0.0 to 10.0 (1 decimal place). "
                    "Omit to clear the override and revert to the auto-calculated CVSS value."
                )
            ),
        ] = None,
        override_none: Annotated[
            bool,
            Query(
                description=(
                    "Set to true to explicitly override risk to None (no risk score). "
                    "Takes precedence over the risk parameter."
                )
            ),
        ] = False,
    ) -> dict:
        """
        Manually set or clear an asset's risk score.

        Three modes:
          - risk=<float>       → override risk to the given value (0.0–10.0, 1 decimal).
          - override_none=true → override risk to None (e.g. "no risk score").
          - (omit both)        → clear the override and revert to the CVSS-derived
                                 value from finding_max_severity.
        """
        asset = await self.root._get_asset(host=host, fields=["finding_max_severity"])
        if not asset:
            raise self.BBOTServerNotFoundError(f"Asset {host} not found")

        if override_none:
            # Explicit override to None
            update = {"risk": None, "risk_override": True}
            description = f"Risk manually set to [bold]None[/bold] on [bold]{host}[/bold]"
        elif risk is not None:
            # Override to a specific float value
            if risk < 0.0 or risk > 10.0:
                raise self.BBOTServerValueError("risk must be between 0.0 and 10.0")
            risk = round(risk, 1)
            update = {"risk": risk, "risk_override": True}
            description = f"Risk manually set to [bold]{risk}[/bold] on [bold]{host}[/bold]"
        else:
            # Clear the override: revert to CVSS-derived value
            finding_max_severity = asset.get("finding_max_severity", None)
            reverted_risk = SEVERITY_TO_CVSS.get(finding_max_severity) if finding_max_severity else None
            update = {"risk": reverted_risk, "risk_override": False}
            description = f"Risk override cleared on [bold]{host}[/bold], reverted to [bold]{reverted_risk}[/bold]"

        await self.root._update_asset(host, update)
        await self.emit_activity(
            type="RISK_UPDATED",
            description=description,
            detail={"host": host, **update},
        )
        return {"host": host, "risk": update["risk"], "risk_override": update["risk_override"]}

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
        # inherit scope from the parent asset so as to make sure that target_id filtering works
        if asset and hasattr(asset, "scope"):
            finding.scope = asset.scope
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
            - severity counts by host
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

        if finding_severities:
            severities_by_host[asset.host] = dict(sorted(finding_severities.items(), key=lambda x: x[1], reverse=True))

        finding_stats["names"] = dict(sorted(name_stats.items(), key=lambda x: x[1], reverse=True))
        finding_stats["counts_by_host"] = dict(sorted(counts_by_host.items(), key=lambda x: x[1], reverse=True))
        finding_stats["severities_by_host"] = dict(
            sorted(severities_by_host.items(), key=lambda x: sum(x[1].values()), reverse=True)
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
            fields=[],
        )
        if existing_finding:
            # update the modified field
            await self.collection.update_one(
                query,
                {
                    "$set": {
                        "modified": self.helpers.utc_now(),
                        "severity": finding.severity,
                        "severity_score": finding.severity_score,
                        "confidence": finding.confidence,
                        "confidence_score": finding.confidence_score,
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
            asset.finding_max_severity = SeverityScore.to_str(asset.finding_max_severity_score)
        else:
            asset.finding_max_severity_score = 0
            asset.finding_max_severity = None
        # Auto-sync risk from finding_max_severity when not manually overridden.
        old_risk = getattr(asset, "risk", None)
        if not getattr(asset, "risk_override", False):
            if asset.finding_max_severity is not None:
                asset.risk = SEVERITY_TO_CVSS[asset.finding_max_severity]
            else:
                asset.risk = None

        # insert the new vulnerability
        await self.root._insert_asset(finding.model_dump())

        severity_color = SEVERITY_COLORS[finding.severity_score]

        activities = [
            self.make_activity(
                type="NEW_FINDING",
                description=f"New finding with severity [bold {severity_color}]{finding.severity}[/bold {severity_color}]: [[bold {severity_color}]{finding.name}[/bold {severity_color}]] on [bold]{finding.host}[/bold]",
                event=event,
                detail=finding.model_dump(),
            )
        ]

        # emit RISK_UPDATED if risk actually changed
        if asset.risk != old_risk:
            activities.append(
                self.make_activity(
                    type="RISK_UPDATED",
                    description=f"Risk updated from [bold]{old_risk}[/bold] to [bold]{asset.risk}[/bold] on [bold]{asset.host}[/bold]",
                    detail={"host": asset.host, "risk": asset.risk, "old_risk": old_risk},
                )
            )

        return activities
