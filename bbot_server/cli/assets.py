from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand


class Assets(BaseBBCTL):
    command = "assets"
    help = "Query, tail, or export BBOT assets"
    epilog = "Query, tail, or export BBOT assets"

    @subcommand(help="List BBOT assets")
    def list(
        self,
        json: common.json = False,
        csv: common.csv = False,
    ):
        asset_list = list(self.bbot_server.get_assets())

        if json:
            for asset in asset_list:
                self.sys.stdout.buffer.write(self.orjson.dumps(asset.model_dump()) + b"\n")
            return

        if csv:
            for line in self.json_to_csv(asset_list, fieldnames=["host", "open_ports"]):
                self.sys.stdout.buffer.write(line)
            return

        table = self.Table()
        table.add_column("Host", style="bold dark_orange")
        table.add_column("Open Ports")
        for asset in asset_list:
            open_ports = ", ".join(getattr(asset, "open_ports", []))
            table.add_row(
                asset.host,
                open_ports,
            )
        self.stdout.print(table)
