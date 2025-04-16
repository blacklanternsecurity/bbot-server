from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand


class TargetCTL(BaseBBCTL):
    command = "target"
    help = "Manage BBOT targets"
    epilog = "Create, start, and monitor BBOT targets"

    @subcommand(help="List preconfigured targets")
    def list(
        self,
        json: common.json = False,
        csv: common.csv = False,
    ):
        target_list = self.bbot_server.get_targets()

        if json:
            for target in target_list:
                self.sys.stdout.buffer.write(self.orjson.dumps(target.model_dump()))
            return

        if csv:
            target_list = [
                {
                    "name": target.name,
                    "description": target.description,
                    "seeds": target.seed_size,
                    "whitelist": target.whitelist_size,
                    "blacklist": target.blacklist_size,
                    "created": self.timestamp_to_human(target.created),
                    "modified": self.timestamp_to_human(target.modified),
                }
                for target in target_list
            ]
            for line in self.json_to_csv(
                target_list,
                fieldnames=["name", "description", "seeds", "whitelist", "blacklist", "created", "modified"],
            ):
                self.sys.stdout.buffer.write(line)
            return

        table = self.Table()
        table.add_column("ID", style=self.DARK_COLOR)
        table.add_column("Name", style=self.COLOR)
        table.add_column("Description")
        table.add_column("Seeds")
        table.add_column("Whitelist")
        table.add_column("Blacklist")
        table.add_column("Created", style=self.DARK_COLOR)
        table.add_column("Modified", style=self.DARK_COLOR)
        for target in target_list:
            table.add_row(
                str(target.id),
                target.name,
                target.description,
                f"{target.seed_size:,}",
                f"{target.whitelist_size:,}",
                f"{target.blacklist_size:,}",
                self.timestamp_to_human(target.created),
                self.timestamp_to_human(target.modified),
            )
        self.stdout.print(table)
