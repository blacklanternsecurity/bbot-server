import typer
from typing import Annotated

from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand
from bbot_server.modules.findings.findings_models import SEVERITY_COLORS, SeverityScore


class FindingCTL(BaseBBCTL):
    command = "finding"
    help = "Query and export BBOT findings"
    short_help = "Query and export BBOT findings"
    attach_to = "bbctl"

    @subcommand(help="List all findings")
    def list(
        self,
        json: common.json = False,
        search: Annotated[
            str, typer.Option("--search", "-s", help="search for a finding by name or description")
        ] = None,
        host: common.host = None,
        domain: common.domain = None,
        target_id: common.target = None,
        min_severity: Annotated[str, typer.Option("--min-severity", "-m", help="minimum severity")] = "INFO",
        max_severity: Annotated[str, typer.Option("--max-severity", "-M", help="maximum severity")] = "CRITICAL",
    ):
        min_severity = SeverityScore.to_score(min_severity.strip().upper())
        max_severity = SeverityScore.to_score(max_severity.strip().upper())

        findings = self.bbot_server.list_findings(
            host=host,
            domain=domain,
            target_id=target_id,
            search=search,
            min_severity=min_severity,
            max_severity=max_severity,
        )

        if json:
            for finding in findings:
                self.print_pydantic_json(finding)
            return

        table = self.Table()
        table.add_column("Severity", style="bold")
        table.add_column("Name", style=self.COLOR)
        table.add_column("Host", style="bold")
        table.add_column("Description")
        table.add_column("Last Seen", style=self.DARK_COLOR)
        for finding in findings:
            severity_color = SEVERITY_COLORS[finding.severity_score]
            table.add_row(
                f"[{severity_color}]{finding.severity}[/{severity_color}]",
                finding.name,
                finding.netloc,
                finding.description,
                self.timestamp_to_human(finding.modified),
            )
        self.stdout.print(table)
