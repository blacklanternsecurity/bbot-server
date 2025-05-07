from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand, Option, Annotated


class AssetCTL(BaseBBCTL):
    command = "asset"
    help = "Query, tail, or export BBOT assets"
    short_help = "Query, tail, or export BBOT assets"

    @subcommand(help="List BBOT assets")
    def list(
        self,
        domain: Annotated[str, Option("--domain", "-d", help="Filter by domain or subdomain")] = None,
        target: Annotated[str, Option("--target", "-t", help="Filter by target ID or name")] = None,
        in_scope_only: Annotated[
            bool, Option("--in-scope-only", "-i", help="Only return in-scope assets (assets in your default target)")
        ] = False,
        json: common.json = False,
        csv: common.csv = False,
    ):
        if target is None and in_scope_only:
            target = "DEFAULT"
        asset_list = self.bbot_server.get_assets(domain=domain, target_id=target)

        if json:
            for asset in asset_list:
                self.print_pydantic_json(asset)
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
        table.add_column("Technologies")
        table.add_column("Cloud Providers")
        table.add_column("Findings")
        for asset in asset_list:
            open_ports = [str(port) for port in sorted(getattr(asset, "open_ports", []))]
            table.add_row(
                asset.host,
                ", ".join(open_ports),
                ", ".join(getattr(asset, "technologies", [])),
                ", ".join(getattr(asset, "cloud_providers", [])),
                ", ".join(getattr(asset, "findings", [])),
            )
        self.stdout.print(table)

    @subcommand(help="Get a single asset by its host")
    def get(self, host: str):
        asset = self.bbot_server.get_asset(host)
        self.print_pydantic_json(asset)

    @subcommand(help="Get stats for a given domain or target")
    def stats(
        self,
        domain: Annotated[str, Option("--domain", "-d", help="Filter stats by domain or subdomain")] = None,
        target: Annotated[str, Option("--target", "-t", help="Filter stats by target ID or name")] = None,
    ):
        stats = self.bbot_server.get_stats(domain=domain, target_id=target)
        self.print_raw_line(self.orjson.dumps(stats))
