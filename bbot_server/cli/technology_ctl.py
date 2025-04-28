from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand


class TechnologyCTL(BaseBBCTL):
    command = "technology"
    help = "Query or monitor BBOT technologies"
    short_help = "Query or monitor BBOT technologies"

    @subcommand(help="List all technologies")
    def list(
        self,
        json: common.json = False,
    ):
        if json:
            for technology in self.bbot_server.get_technologies():
                self.sys.stdout.buffer.write(self.orjson.dumps(technology.model_dump()) + b"\n")
            return

        table = self.Table()
        table.add_column("Technology", style=self.COLOR)
        table.add_column("Last Seen", style=self.DARK_COLOR)
        table.add_column("Number of Hosts")
        table.add_column("Hosts", style="bold")
        for t in self.bbot_server.get_technologies_summary():
            table.add_row(
                t["technology"],
                self.timestamp_to_human(t["last_seen"]),
                f"{len(t['hosts']):,}",
                ", ".join(t["hosts"]),
            )
        self.stdout.print(table)
