from bbot_server.cli import common
from bbot_server.utils.misc import timestamp_to_human
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
        for technology, stats in self.bbot_server.get_technologies_summary().items():
            last_seen = stats["last_seen"]
            hosts = stats["hosts"]
            table.add_row(
                technology,
                self.timestamp_to_human(last_seen),
                f"{len(hosts):,}",
                ", ".join(hosts),
            )
        self.stdout.print(table)
