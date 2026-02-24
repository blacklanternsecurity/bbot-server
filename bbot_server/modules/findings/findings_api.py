from fastapi import Query
from typing import Annotated

from bbot_server.applets.base import BaseApplet, api_endpoint
from bbot_server.modules.findings.findings_models import Finding, SEVERITY_COLORS, SeverityScore, FindingsQuery


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
        row = await self._get_one(id=id)
        if not row:
            raise self.BBOTServerNotFoundError("Finding not found")
        return row

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
        async for row in query.query_iter(self):
            yield row

    @api_endpoint("/query", methods=["POST"], type="http_stream", response_model=dict, summary="Query findings")
    async def query_findings(self, query: FindingsQuery | None = None):
        """
        Advanced querying of findings. Choose your own filters and fields.
        """
        async for row in query.query_iter(self):
            d = row.model_dump()
            if query.fields:
                d = {k: v for k, v in d.items() if k in query.fields}
                d["_id"] = None  # backward compat
            yield d

    @api_endpoint("/count", methods=["POST"], summary="Count findings")
    async def count_findings(self, query: FindingsQuery | None = None) -> int:
        """
        Same as query_findings, except only returns the count
        """
        return await query.query_count(self)

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
        query = FindingsQuery(
            domain=domain, target_id=target_id, min_severity=min_severity, max_severity=max_severity, fields=["name"]
        )
        async for row in query.query_iter(self):
            finding_name = row.name
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
            fields=["severity_score"],
        )
        async for row in query.query_iter(self):
            severity = SeverityScore.to_str(row.severity_score)
            findings[severity] = findings.get(severity, 0) + 1
        findings = dict(sorted(findings.items(), key=lambda x: x[1], reverse=True))
        return findings

    async def handle_event(self, event, host):
        name = event.data_json["name"]
        description = event.data_json["description"]
        confidence = event.data_json.get("confidence", 1)
        severity = event.data_json.get("severity", "INFO")
        cves = event.data_json.get("cves", [])
        finding = Finding(
            name=name,
            host=host,
            description=description,
            confidence=confidence,
            severity=severity,
            cves=cves,
            event=event,
        )
        return await self._insert_or_update_finding(finding, event)

    async def _insert_or_update_finding(self, finding: Finding, event=None):
        """
        Insert a new finding into the database, or update an existing one.

        Returns a list of activities. If the finding was new, a NEW_FINDING activity will be returned.
        """
        existing_row = await self._get_one(id=finding.id)
        if existing_row:
            await self._update(
                {"id": finding.id},
                {
                    "modified": self.helpers.utc_now(),
                    "severity_score": finding.severity_score,
                    "confidence_score": finding.confidence_score,
                },
            )
            return []

        # insert the new finding directly
        await self._insert(finding)

        severity_color = SEVERITY_COLORS[finding.severity_score]

        return [
            self.make_activity(
                type="NEW_FINDING",
                description=f"New finding with severity [bold {severity_color}]{finding.severity}[/bold {severity_color}]: [[bold {severity_color}]{finding.name}[/bold {severity_color}]] on [bold]{finding.host}[/bold]",
                event=event,
                detail=finding.model_dump(),
            )
        ]
