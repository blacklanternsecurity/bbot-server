from typer import Option
from typing import Annotated

from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand


class ActivityCTL(BaseBBCTL):
    command = "activity"
    help = "Query or monitor BBOT activities"
    short_help = "Query or monitor BBOT activities"

    @subcommand(help="Tail BBOT server activity")
    def tail(
        self,
        n: Annotated[int, Option("--lines", "-n", help="Number of activities to tail")] = 10,
        json: common.json = False,
    ):
        for a in self.bbot_server.tail_activities(n=n):
            if json:
                self.print_pydantic_json(a)
                continue

            timestamp = self.timestamp_to_human(a.timestamp)
            self.stdout.print(f"[[{self.DARK_COLOR}]{timestamp}[/{self.DARK_COLOR}]] {a.description_colored}")

    @subcommand(help="List BBOT activities")
    def list(
        self,
        host: Annotated[str, Option("--host", "-h", help="Filter by exact host match")] = None,
        type: Annotated[
            str, Option("--type", "-t", help="Filter by activity type, e.g. NEW_OPEN_PORT, NEW_FINDING, etc.")
        ] = None,
        json: common.json = False,
    ):
        activities = self.bbot_server.get_activities(host=host, type=type)

        if json:
            for activity in activities:
                self.print_pydantic_json(activity)
            return

        table = self.Table()
        table.add_column("Type", style=self.COLOR)
        table.add_column("Host")
        table.add_column("Description")
        table.add_column("Timestamp")
        for activity in activities:
            table.add_row(
                activity.type,
                activity.host,
                activity.description_colored,
                self.timestamp_to_human(activity.timestamp),
            )
        self.stdout.print(table)
