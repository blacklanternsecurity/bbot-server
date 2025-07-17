import typer
from typing import Annotated

from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand


class TechnologyCTL(BaseBBCTL):
    command = "technology"
    help = "Query and export BBOT technologies"
    short_help = "Query and export BBOT technologies"
    attach_to = "bbctl"

    @subcommand(help="List all technologies")
    def list(
        self,
        json: common.json = False,
        domain: Annotated[str, typer.Option("--domain", "-d", help="filter by domain (subdomains included)")] = None,
        host: Annotated[str, typer.Option("--host", "-h", help="filter by host")] = None,
        technology: Annotated[
            str, typer.Option("--technology", "-t", help="filter by technology (must match exactly)")
        ] = None,
        target_id: Annotated[
            str, typer.Option("--target", "-t", help="filter by target (can be either name or ID)")
        ] = None,
    ):
        if json:
            for technology in self.bbot_server.get_technologies(
                domain=domain, host=host, technology=technology, target_id=target_id
            ):
                self.print_pydantic_json(technology)
            return

        table = self.Table()
        table.add_column("Technology", style=self.COLOR)
        table.add_column("Number of Hosts")
        table.add_column("Hosts", style="bold")
        table.add_column("Last Seen", style=self.DARK_COLOR)
        for t in self.bbot_server.get_technologies_summary(
            domain=domain, host=host, technology=technology, target_id=target_id
        ):
            table.add_row(
                t["technology"],
                f"{len(t['hosts']):,}",
                ", ".join(t["hosts"]),
                self.timestamp_to_human(t["last_seen"]),
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
        table.add_column("Host and Port", style="bold")
        table.add_column("Last Seen", style=self.DARK_COLOR)
        for technology in self.bbot_server.search_technology(technology, domain=domain, target_id=target_id):
            table.add_row(
                technology.technology,
                technology.netloc,
                self.timestamp_to_human(technology.last_seen),
            )
        self.stdout.print(table)
