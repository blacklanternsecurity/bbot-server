import typer
from typing import Annotated

from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand


class TechnologyCTL(BaseBBCTL):
    command = "technology"
    help = "Query BBOT technologies"
    short_help = "Query BBOT technologies"

    @subcommand(help="List all technologies")
    def list(
        self,
        json: common.json = False,
        domain: Annotated[
            str, typer.Option("--domain", "-d", help="limit results to this domain (subdomains included)")
        ] = None,
        target_id: Annotated[
            str, typer.Option("--target", "-t", help="limit results to this target (can be either name or ID)")
        ] = None,
    ):
        if json:
            for technology in self.bbot_server.get_technologies(domain=domain, target_id=target_id):
                self.print_pydantic_json(technology)
            return

        table = self.Table()
        table.add_column("Technology", style=self.COLOR)
        table.add_column("Last Seen", style=self.DARK_COLOR)
        table.add_column("Number of Hosts")
        table.add_column("Hosts", style="bold")
        for t in self.bbot_server.get_technologies_summary(domain=domain, target_id=target_id):
            table.add_row(
                t["technology"],
                self.timestamp_to_human(t["last_seen"]),
                f"{len(t['hosts']):,}",
                ", ".join(t["hosts"]),
            )
        self.stdout.print(table)

    @subcommand(help="Search for a technology")
    def search(
        self,
        technology: Annotated[str, typer.Argument(help="technology to search for")] = None,
        domain: Annotated[
            str, typer.Option("--domain", "-d", help="limit results to this domain (subdomains included)")
        ] = None,
        target_id: Annotated[
            str, typer.Option("--target", "-t", help="limit results to this target (either name or ID)")
        ] = None,
        json: common.json = False,
    ):
        if json:
            for technology in self.bbot_server.search_technology(technology, domain=domain, target_id=target_id):
                self.print_pydantic_json(technology)
            return

        table = self.Table()
        table.add_column("Technology", style=self.COLOR)
        table.add_column("Last Seen", style=self.DARK_COLOR)
        table.add_column("Host and Port", style="bold")
        for technology in self.bbot_server.search_technology(technology, domain=domain, target_id=target_id):
            table.add_row(
                technology.technology,
                self.timestamp_to_human(technology.last_seen),
                technology.netloc,
            )
        self.stdout.print(table)
