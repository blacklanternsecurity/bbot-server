from typing import Annotated
from typer import Option, Argument

from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand


class ScanCTL(BaseBBCTL):
    command = "scan"
    help = "Create, start, and monitor BBOT scans"
    short_help = "Manage BBOT scans, targets, and presets"
    attach_to = "bbctl"

    @subcommand(help="List scans")
    def list(
        self,
        json: common.json = False,
        csv: common.csv = False,
    ):
        scans = self.bbot_server.get_scans()

        if json:
            for scan in scans:
                self.print_pydantic_json(scan)
            return

        if csv:

            def iter_scans():
                for scan in scans:
                    scan_json = scan.model_dump()
                    duration = scan_json.get("duration_seconds", None)
                    started = scan_json.get("started_at", None)
                    finished = scan_json.get("finished_at", None)

                    out_json = {}
                    out_json["name"] = scan_json["name"]
                    out_json["status"] = scan_json["status"]
                    out_json["target"] = scan_json["target"]["name"]
                    out_json["preset"] = scan_json["preset"]["name"]
                    out_json["duration"] = self.seconds_to_human(duration) if duration is not None else ""
                    out_json["started"] = self.timestamp_to_human(started) if started is not None else ""
                    out_json["finished"] = self.timestamp_to_human(finished) if finished is not None else ""
                    out_json["id"] = scan_json["id"]
                    yield out_json

            for line in common.json_to_csv(
                iter_scans(),
                fieldnames=[
                    "name",
                    "status",
                    "target",
                    "preset",
                    "duration",
                    "started",
                    "finished",
                    "id",
                ],
            ):
                self.sys.stdout.buffer.write(line)
            return

        table = self.Table()
        table.add_column("Name", style=self.COLOR)
        table.add_column("Status", style="bold")
        table.add_column("Target")
        table.add_column("Preset", style=self.COLOR)
        table.add_column("Started", style=self.DARK_COLOR)
        table.add_column("Finished", style=self.DARK_COLOR)
        table.add_column("Duration")
        table.add_column("ID", style=self.DARK_COLOR)
        # TODO: why is duration None?
        for scan in scans:
            duration = "" if scan.duration_seconds is None else self.seconds_to_human(scan.duration_seconds)
            started = "" if scan.started_at is None else self.timestamp_to_human(scan.started_at)
            finished = "" if scan.finished_at is None else self.timestamp_to_human(scan.finished_at)
            target_name = f"[{self.COLOR}]{scan.target.name}[/{self.COLOR}]"
            for attr, friendly_attr in (
                ("target_size", "Target"),
                ("seed_size", "Seeds"),
                ("blacklist_size", "Blacklist"),
            ):
                if getattr(scan.target, attr):
                    target_name += (
                        f" [{self.DARK_COLOR}]({friendly_attr}: {getattr(scan.target, attr):,})[/{self.DARK_COLOR}]"
                    )
            table.add_row(
                scan.name,
                scan.status,
                target_name,
                scan.preset.name,
                started,
                finished,
                duration,
                scan.id,
            )
        self.stdout.print(table)

    @subcommand(help="Start a new scan")
    def start(
        self,
        target: Annotated[str, Option("--target", "-t", help="Target name or ID to scan", metavar="TARGET")],
        preset: Annotated[
            str,
            Option(
                "--preset",
                "-p",
                help="Preset name or ID to use for the scan",
                metavar="PRESET",
            ),
        ],
        name: Annotated[str, Option("--name", "-n", help="Name of the scan", metavar="NAME")] = None,
    ):
        scan = self.bbot_server.start_scan(name=name, target_id=target, preset_id=preset)
        self.log.info(f"Scan queued successfully")
        self.print_pydantic_json(scan, colorize=True)

    @subcommand(help="Cancel a scan")
    def cancel(
        self,
        scan_id: Annotated[str, Argument(help="Scan ID to cancel")],
    ):
        self.bbot_server.cancel_scan(scan_id)
        self.log.info(f"Scan cancelled successfully")
