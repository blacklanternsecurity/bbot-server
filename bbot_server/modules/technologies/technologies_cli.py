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
        search: Annotated[str, typer.Option("--search", "-s", help="search for a technology (fuzzy match)")] = None,
        target_id: Annotated[
            str, typer.Option("--target", "-t", help="filter by target (can be either name or ID)")
        ] = None,
        sort: Annotated[str, typer.Option("--sort", help="field to sort by")] = ["-last_seen"],
    ):
        technologies = self.bbot_server.list_technologies(
            domain=domain, host=host, technology=technology, target_id=target_id, search=search, sort=sort
        )

        if json:
            for technology in technologies:
                self.print_pydantic_json(technology)
            return

        table = self.Table()
        table.add_column("Technology", style=self.COLOR)
        table.add_column("Host and Port", style="bold")
        table.add_column("Last Seen", style=self.DARK_COLOR)
        for t in technologies:
            table.add_row(
                t.technology,
                t.netloc,
                self.timestamp_to_human(t.last_seen),
            )
        self.stdout.print(table)

    @subcommand(help="Summarize technologies")
    def summarize(
        self,
        json: common.json = False,
        domain: Annotated[str, typer.Option("--domain", "-d", help="filter by domain (subdomains included)")] = None,
        host: Annotated[str, typer.Option("--host", "-h", help="filter by host")] = None,
        technology: Annotated[
            str, typer.Option("--technology", "-t", help="filter by technology (must match exactly)")
        ] = None,
        target_id: Annotated[str, typer.Option("--target", help="filter by target (can be either name or ID)")] = None,
        limit: Annotated[
            int,
            typer.Option("--limit", "-l", help="limit the number of results (most prevalent results are shown first)"),
        ] = None,
    ):
        if limit is not None and limit < 1:
            raise self.BBOTServerValueError("Limit must be greater than 0")

        summary = self.bbot_server.get_technologies_summary(
            domain=domain, host=host, technology=technology, target_id=target_id
        )
        if json:
            for technology in summary[:limit]:
                self.print_json(technology)
            return

        table = self.Table()
        table.add_column("Technology", style=self.COLOR)
        table.add_column("Number of Hosts")
        table.add_column("Hosts", style="bold")
        table.add_column("Last Seen", style=self.DARK_COLOR)
        for t in summary[:limit]:
            table.add_row(
                t["technology"],
                f"{len(t['hosts']):,}",
                ", ".join(t["hosts"]),
                self.timestamp_to_human(t["last_seen"]),
            )
        self.stdout.print(table)
