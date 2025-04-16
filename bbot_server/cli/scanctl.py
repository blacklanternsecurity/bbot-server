import yaml
from typer import Option
from pathlib import Path
from typing import Annotated

from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand

from bbot_server.cli.scanrunsctl import ScanRunsCTL


class ScanCTL(BaseBBCTL):
    command = "scan"
    help = "Create, start, and monitor BBOT scans"
    short_help = "Manage BBOT scans"

    include = [ScanRunsCTL]

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
        preset: Annotated[
            Path,
            Option(
                "--preset",
                "-p",
                help="BBOT preset YAML file to use for the scan. Must include target.",
                metavar="PRESET",
            ),
        ],
        name: Annotated[str, Option("--name", "-n", help="Name of the scan", metavar="NAME")] = None,
    ):
        if not preset.resolve().is_file():
            raise self.BBOTServerNotFoundError(f"Unable to find preset file at {preset}")
        preset = yaml.safe_load(preset.read_text())
        targets = preset.pop("targets", [])
        whitelist = preset.pop("whitelist", [])
        blacklist = preset.pop("blacklist", [])
        strict_dns_scope = preset.get("scope", {}).get("strict_dns", False)
        try:
            target = self.bbot_server.create_target(
                target=targets, whitelist=whitelist, blacklist=blacklist, strict_dns_scope=strict_dns_scope
            )
        except self.BBOTServerValueError as e:
            error = e.detail.get("error", "")
            if "Identical target already exists" in error:
                hash = e.detail.get("hash")
                target = self.bbot_server.get_target(hash=hash)
            raise
        scan = self.bbot_server.create_scan(name=name, target=str(target.id))
        self.sys.stdout.buffer.write(self.orjson.dumps(scan.model_dump()))
