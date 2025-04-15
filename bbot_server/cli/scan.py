from uuid import UUID
from typer import Option
from typing import Annotated

from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand

class Scans(BaseBBCTL):
    command = "scan"
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
                self.sys.stdout.buffer.write(self.orjson.dumps(scan.model_dump()))
            return

        if csv:
            for line in self.json_to_csv(scan_list, fieldnames=["name", "targets"]):
                self.sys.stdout.buffer.write(line)
            return

        table = self.Table()
        table.add_column("Name", style=self.COLOR)
        table.add_column("Targets")
        for scan in scan_list:
            table.add_row(scan.name, ", ".join(scan.target))
        self.stdout.print(table)

    @subcommand(help="Create a new scan")
    def create(
        self,
        name: Annotated[str, Option("--name", "-n", help="Name of the scan", metavar="NAME")],
        target: Annotated[str, Option("--target", "-t", help="Target name or id of the scan", metavar="TARGET")],
    ):
        try:
            target_id = UUID(target)
        except ValueError:
            target = self.bbot_server.get_target(name=target)
            target_id = target.id

        scan = self.bbot_server.create_scan(name=name, target=str(target_id))
        self.sys.stdout.buffer.write(self.orjson.dumps(scan.model_dump()))
