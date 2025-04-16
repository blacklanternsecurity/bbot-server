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

        # table = self.Table()
        # table.add_column("Name", style=self.COLOR)
        # table.add_column("Targets")
        # for scan_run in scan_runs:
        #     table.add_row(scan_run.name, ", ".join(scan_run.target))
        # self.stdout.print(table)
