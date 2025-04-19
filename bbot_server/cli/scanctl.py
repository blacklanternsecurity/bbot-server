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
        table.add_column("Seeds")
        table.add_column("Whitelist")
        table.add_column("Blacklist")
        table.add_column("Created", style=self.DARK_COLOR)
        table.add_column("Modified", style=self.DARK_COLOR)
        for scan in scan_list:
            table.add_row(
                scan.name,
                f"{scan.target.seed_size:,}",
                f"{scan.target.whitelist_size:,}",
                f"{scan.target.blacklist_size:,}",
                self.timestamp_to_human(scan.created),
                self.timestamp_to_human(scan.modified),
            )
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
                seeds=targets, whitelist=whitelist, blacklist=blacklist, strict_dns_scope=strict_dns_scope
            )
        except self.BBOTServerValueError as e:
            error = e.detail.get("error", "")
            if "Identical target already exists" in error:
                hash = e.detail.get("hash")
                target = self.bbot_server.get_target(hash=hash)
            raise
        scan = self.bbot_server.create_scan(name=name, target_id=str(target.id))
        self.sys.stdout.buffer.write(self.orjson.dumps(scan.model_dump()))

    @subcommand(help="Start a scan")
    def start(
        self,
        name: Annotated[str, Option("--name", "-n", help="Name of the scan", metavar="NAME")] = None,
        id: Annotated[str, Option("--id", "-i", help="ID of the scan", metavar="ID")] = None,
        agent_name: Annotated[
            str, Option("--agent-name", "-an", help="Agent name to use for the scan", metavar="AGENT_NAME")
        ] = None,
        agent_id: Annotated[
            str, Option("--agent-id", "-ai", help="Agent ID to use for the scan", metavar="AGENT_ID")
        ] = None,
    ):
        if name is None and id is None:
            raise self.BBOTServerError("Must provide either a scan name or id")
        scan = self.bbot_server.get_scan(name=name, id=id)
        if agent_name or agent_id:
            agent = self.bbot_server.get_agent(name=agent_name, id=agent_id)
            agent_id = agent.id
        self.bbot_server.start_scan(scan.id, agent_id)
        self.log.info(f"Scan {scan.name} successfully queued")
