from pathlib import Path

from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand, Option, Annotated


class TargetCTL(BaseBBCTL):
    command = "target"
    help = "Create, start, and monitor BBOT targets"
    short_help = "Manage BBOT targets"

    @subcommand(help="Create a new target")
    def create(
        self,
        seeds: Annotated[Path, Option("--seeds", "-s", help="File containing seeds")],
        whitelist: Annotated[
            Path,
            Option(
                "--whitelist",
                "-w",
                help="File containing whitelist. If not provided, the seeds will be used as the whitelist.",
            ),
        ] = None,
        blacklist: Annotated[Path, Option("--blacklist", "-b", help="File containing blacklist")] = None,
        name: Annotated[str, Option("--name", "-n", help="Target name")] = "",
        description: Annotated[str, Option("--description", "-d", help="Target description")] = "",
        strict_dns_scope: Annotated[
            bool,
            Option(
                "--strict-scope",
                "-s",
                help="Strict DNS scope (only the exact hosts themselves are in scope, not their children)",
            ),
        ] = False,
    ):
        seeds = self._read_file(seeds, "seeds")
        whitelist = None if not whitelist else self._read_file(whitelist, "whitelist")
        blacklist = None if not blacklist else self._read_file(blacklist, "blacklist")
        target = self.bbot_server.create_target(
            name=name,
            description=description,
            seeds=seeds,
            whitelist=whitelist,
            blacklist=blacklist,
            strict_dns_scope=strict_dns_scope,
        )
        self.log.info(f"Target created successfully:")
        self.stdout.print_json(target.model_dump_json())

    @subcommand(help="Delete a target")
    def delete(
        self,
        name: Annotated[str, Option("--name", "-n", help="Target name")] = None,
        id: Annotated[str, Option("--id", "-i", help="Target ID")] = None,
    ):
        if name is None and id is None:
            raise self.BBOTServerValueError("Must provide either a target name or ID")
        self.bbot_server.delete_target(name=name, id=id)
        self.log.info(f"Target deleted successfully")

    @subcommand(help="List preconfigured targets")
    def list(
        self,
        json: common.json = False,
        csv: common.csv = False,
    ):
        target_list = self.bbot_server.get_targets()

        if json:
            for target in target_list:
                self.sys.stdout.buffer.write(self.orjson.dumps(target.model_dump()) + b"\n")
            return

        if csv:
            target_list = [
                {
                    "name": target.name,
                    "description": target.description,
                    "seeds": target.seed_size,
                    "whitelist": target.whitelist_size,
                    "blacklist": target.blacklist_size,
                    "strict_scope": "Yes" if target.strict_dns_scope else "No",
                    "created": self.timestamp_to_human(target.created),
                    "modified": self.timestamp_to_human(target.modified),
                }
                for target in target_list
            ]
            for line in common.json_to_csv(
                target_list,
                fieldnames=[
                    "name",
                    "description",
                    "seeds",
                    "whitelist",
                    "blacklist",
                    "strict_scope",
                    "created",
                    "modified",
                ],
            ):
                self.sys.stdout.buffer.write(line)
            return

        table = self.Table()
        table.add_column("Name", style=self.COLOR)
        table.add_column("Description")
        table.add_column("Seeds")
        table.add_column("Whitelist")
        table.add_column("Blacklist")
        table.add_column("Strict Scope")
        table.add_column("Created", style=self.DARK_COLOR)
        table.add_column("Modified", style=self.DARK_COLOR)
        for target in target_list:
            table.add_row(
                target.name,
                target.description,
                f"{target.seed_size:,}",
                f"{target.whitelist_size:,}",
                f"{target.blacklist_size:,}",
                "Yes" if target.strict_dns_scope else "No",
                self.timestamp_to_human(target.created),
                self.timestamp_to_human(target.modified),
            )
        self.stdout.print(table)

    def _read_file(self, file, filetype):
        if not file.resolve().is_file():
            raise self.BBOTServerValueError(f"Unable to find {filetype} at {file}")
        lines = []
        for line in file.read_text().splitlines():
            line = line.strip()
            if line:
                lines.append(line)
        return lines
