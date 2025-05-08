import typer
from typing import Annotated

from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand
from bbot_server.models.finding_models import SEVERITY_COLORS


class FindingCTL(BaseBBCTL):
    command = "finding"
    help = "Query BBOT findings"
    short_help = "Query BBOT findings"

    @subcommand(help="List all findings")
    def list(
        self,
        json: common.json = False,
        search: Annotated[
            str, typer.Option("--search", "-s", help="search for a finding by name or description")
        ] = None,
        domain: Annotated[
            str, typer.Option("--domain", "-d", help="limit results to this domain (subdomains included)")
        ] = None,
        target_id: Annotated[
            str, typer.Option("--target", "-t", help="limit results to this target (can be either name or ID)")
        ] = None,
    ):
        if json:
            for finding in self.bbot_server.get_findings(domain=domain, target_id=target_id, search=search):
                self.print_pydantic_json(finding)
            return

        table = self.Table()
        table.add_column("Severity", style="bold")
        table.add_column("Name", style=self.COLOR)
        table.add_column("Host", style="bold")
        table.add_column("Description")
        table.add_column("Last Seen", style=self.DARK_COLOR)
        for finding in self.bbot_server.get_findings(domain=domain, target_id=target_id, search=search):
            severity_color = SEVERITY_COLORS[finding.severity_score]
            table.add_row(
                f"[{severity_color}]{finding.severity}[/{severity_color}]",
                finding.name,
                finding.netloc,
                finding.description,
                self.timestamp_to_human(finding.modified),
            )
        self.stdout.print(table)
