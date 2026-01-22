from pathlib import Path
from typer import Argument

from bbot_server.cli import common
from bbot_server.modules.targets.targets_models import CreateTarget
from bbot_server.cli.base import BaseBBCTL, subcommand, Option, Annotated


class TargetCTL(BaseBBCTL):
    command = "target"
    help = "Create, start, and monitor BBOT targets"
    short_help = "Manage BBOT targets"
    attach_to = "scan"

    @subcommand(help="Create a new target")
    def create(
        self,
        target: Annotated[
            Path,
            Option(
                "--target",
                "-t",
                help="File containing target. This determines what's in-scope.",
            ),
        ] = None,
        seeds: Annotated[
            Path, Option("--seeds", "-s", help="File containing seeds. If not specified, will be copied from target.")
        ] = None,
        blacklist: Annotated[Path, Option("--blacklist", "-b", help="File containing blacklist")] = None,
        name: Annotated[str, Option("--name", "-n", help="Target name")] = "",
        description: Annotated[str, Option("--description", "-d", help="Target description")] = "",
        strict_dns_scope: Annotated[
            bool,
            Option(
                "--strict-scope",
                "-ss",
                help="Strict DNS scope (only the exact hosts themselves should be considered in-scope, not their subdomains)",
            ),
        ] = False,
        allow_duplicates: Annotated[
            bool,
            Option(
                "--allow-duplicates",
                "-ad",
                help="Allow a target to be created even if there's already an identical one",
            ),
        ] = False,
    ):
        seeds = None if not seeds else self._read_file(seeds, "seeds")
        target = [] if not target else self._read_file(target, "target")
        blacklist = None if not blacklist else self._read_file(blacklist, "blacklist")
        target = CreateTarget(
            name=name,
            description=description,
            target=target,
            seeds=seeds,
            blacklist=blacklist,
            strict_dns_scope=strict_dns_scope,
        )
        target = self.bbot_server.create_target(target, allow_duplicate_hash=allow_duplicates)
        self.log.info(f"Target created successfully:")
        self.print_json(target.model_dump(), colorize=True)

    @subcommand(help="Delete a target")
    def delete(
        self,
        id: Annotated[str, Argument(help="Target name or ID")],
    ):
        self.bbot_server.delete_target(id=id)
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
                self.print_pydantic_json(target)
            return

        if csv:
            target_list = [
                {
                    "name": target.name,
                    "description": target.description,
                    "target": target.target_size,
                    "seeds": target.seed_size,
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
                    "target",
                    "seeds",
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
        table.add_column("Target")
        table.add_column("Seeds")
        table.add_column("Blacklist")
        table.add_column("Strict Scope")
        table.add_column("Created", style=self.DARK_COLOR)
        table.add_column("Modified", style=self.DARK_COLOR)
        for target in target_list:
            table.add_row(
                target.name,
                target.description,
                f"{target.target_size:,}",
                f"{target.seed_size:,}",
                f"{target.blacklist_size:,}",
                "Yes" if target.strict_dns_scope else "No",
                self.timestamp_to_human(target.created),
                self.timestamp_to_human(target.modified),
            )
        self.stdout.print(table)

    @subcommand(help="Get a target by its name or ID")
    def get(self, target_id: Annotated[str, Argument(help="Target name or ID")]):
        target = self.bbot_server.get_target(target_id)
        self.print_json(target.model_dump(), colorize=True)

    def _read_file(self, file, filetype):
        if not file.resolve().is_file():
            raise self.BBOTServerValueError(f"Unable to find {filetype} at {file}")
        lines = []
        for line in file.read_text().splitlines():
            line = line.strip()
            if line:
                lines.append(line)
        return lines
