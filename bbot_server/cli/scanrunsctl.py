from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand


class ScanRunsCTL(BaseBBCTL):
    command = "runs"
    help = "View individual BBOT scan runs"
    short_help = "View individual BBOT scan runs"

    @subcommand(help="List scan runs")
    def list(
        self,
        json: common.json = False,
        csv: common.csv = False,
    ):
        scan_runs = self.bbot_server.get_scan_runs()

        if json:
            for scan_run in scan_runs:
                self.sys.stdout.buffer.write(self.orjson.dumps(scan_run.model_dump()) + b"\n")
            return

        if csv:

            def iter_scan_runs():
                for scan_run in scan_runs:
                    out_json = {}
                    scan_run_json = scan_run.model_dump()
                    out_json["name"] = scan_run_json["name"]
                    out_json["status"] = scan_run_json["status"]
                    out_json["seeds"] = f"{scan_run_json['target']['seed_size']:,}"
                    out_json["whitelist"] = f"{scan_run_json['target']['whitelist_size']:,}"
                    out_json["blacklist"] = f"{scan_run_json['target']['blacklist_size']:,}"
                    out_json["duration"] = self.seconds_to_human(scan_run_json["duration_seconds"])
                    out_json["started"] = self.timestamp_to_human(scan_run_json["started_at"])
                    out_json["finished"] = self.timestamp_to_human(scan_run_json["finished_at"])
                    yield out_json

            for line in common.json_to_csv(
                iter_scan_runs(),
                fieldnames=[
                    "name",
                    "status",
                    "seeds",
                    "whitelist",
                    "blacklist",
                    "duration",
                    "started",
                    "finished",
                ],
            ):
                self.sys.stdout.buffer.write(line)
            return

        table = self.Table()
        table.add_column("Name", style=self.COLOR)
        table.add_column("Status", style="bold")
        table.add_column("Started", style=self.DARK_COLOR)
        table.add_column("Finished", style=self.DARK_COLOR)
        table.add_column("Duration")
        table.add_column("Seeds")
        table.add_column("Whitelist")
        table.add_column("Blacklist")

        # TODO: why is duration None?
        for scan_run in scan_runs:
            duration = "" if scan_run.duration_seconds is None else self.seconds_to_human(scan_run.duration_seconds)
            started = "" if scan_run.started_at is None else self.timestamp_to_human(scan_run.started_at)
            finished = "" if scan_run.finished_at is None else self.timestamp_to_human(scan_run.finished_at)
            table.add_row(
                scan_run.name,
                scan_run.status,
                started,
                finished,
                duration,
                f"{scan_run.target.seed_size:,}",
                f"{scan_run.target.whitelist_size:,}",
                f"{scan_run.target.blacklist_size:,}",
            )
        self.stdout.print(table)
