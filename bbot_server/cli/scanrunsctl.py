from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand


class ScanRunsCTL(BaseBBCTL):
    command = "runs"
    help = "View individual BBOT scan runs"
    epilog = "View individual BBOT scan runs"

    @subcommand(help="List scan runs")
    def list(
        self,
        json: common.json = False,
        csv: common.csv = False,
    ):
        scan_runs = self.bbot_server.get_scan_runs()

        if json:
            for scan_run in scan_runs:
                self.sys.stdout.buffer.write(self.orjson.dumps(scan_run.model_dump()))
            return

        # if csv:
        #     for line in self.json_to_csv(scan_runs, fieldnames=["name", "targets"]):
        #         self.sys.stdout.buffer.write(line)
        #     return

        table = self.Table()
        table.add_column("Name", style=self.COLOR)
        table.add_column("Status", style="bold")
        table.add_column("Targets")
        table.add_column("Whitelist")
        table.add_column("Blacklist")
        table.add_column("Duration")
        table.add_column("Started", style=self.DARK_COLOR)
        table.add_column("Finished", style=self.DARK_COLOR)

        for scan_run in scan_runs:
            table.add_row(
                scan_run.name,
                scan_run.status,
                f"{scan_run.target.seed_size:,}",
                f"{scan_run.target.whitelist_size:,}",
                f"{scan_run.target.blacklist_size:,}",
                self.seconds_to_human(scan_run.duration_seconds),
                self.timestamp_to_human(scan_run.started_at),
                self.timestamp_to_human(scan_run.finished_at),
            )
        self.stdout.print(table)
