from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand


class AssetCTL(BaseBBCTL):
    command = "asset"
    help = "Query, tail, or export BBOT assets"
    short_help = "Query, tail, or export BBOT assets"

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

            def iter_assets():
                for asset in asset_list:
                    asset_dict = {}
                    asset_dict["host"] = asset.host
                    asset_dict["open_ports"] = ",".join(
                        [str(port) for port in sorted(getattr(asset, "open_ports", []))]
                    )
                    asset_dict["modified"] = self.timestamp_to_human(asset.modified)
                    yield asset_dict

            for line in common.json_to_csv(iter_assets(), fieldnames=["host", "open_ports", "modified"]):
                self.sys.stdout.buffer.write(line)
            return

        table = self.Table()
        table.add_column("Host", style=self.COLOR)
        table.add_column("Open Ports")
        table.add_column("Modified", style=self.DARK_COLOR)
        for asset in asset_list:
            open_ports = [str(port) for port in sorted(getattr(asset, "open_ports", []))]
            table.add_row(
                asset.host,
                ",".join(open_ports),
                self.timestamp_to_human(asset.modified),
            )
        self.stdout.print(table)
