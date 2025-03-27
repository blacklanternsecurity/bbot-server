from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand


class Scans(BaseBBCTL):
    command = "scans"
    help = "Manage BBOT scans"
    epilog = "Create, start, and monitor BBOT scans"

    @subcommand(help="List preconfigured scans")
    def list(
        self,
        json: common.json = False,
        csv: common.csv = False,
    ):
        scan_list = self.bbot_server.get_scans()

        if json:
            for scan in scan_list:
                self.sys.stderr.buffer.write(self.orjson.dumps(scan))
            return

        if csv:
            for line in self.json_to_csv(scan_list, fieldnames=["name", "targets"]):
                self.sys.stdout.buffer.write(line)
            return

        table = self.Table()
        table.add_column("Name", style="bold dark_orange")
        table.add_column("Targets")
        for scan in scan_list:
            table.add_row(scan.name, ", ".join(scan.target))
        self.stdout.print(table)
