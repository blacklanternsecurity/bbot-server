from bbot_server.cli import common
from bbot_server.utils.misc import timestamp_to_human
from bbot_server.cli.base import BaseBBCTL, subcommand


class ActivityCTL(BaseBBCTL):
    command = "activity"
    help = "Query or monitor BBOT activities"
    epilog = "Query or monitor BBOT activities"

    @subcommand(help="Tail BBOT server activity")
    def tail(
        self,
        n: int = 10,
        json: common.json = False,
    ):
        for a in self.bbot_server.tail_activities(n=n):
            if json:
                self.sys.stdout.buffer.write(self.orjson.dumps(a.model_dump()) + b"\n")
                continue

            timestamp = timestamp_to_human(a.timestamp)
            self.stdout.print(f"[[bright_black]{timestamp}[/bright_black]] {a.description_colored}")
