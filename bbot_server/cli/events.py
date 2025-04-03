from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand


class Events(BaseBBCTL):
    command = "events"
    help = "Query, tail, or ingest BBOT events"
    epilog = "Query, tail, or ingest BBOT events"

    @subcommand(help="List preconfigured scans")
    def list(
        self,
        json: common.json = False,
        csv: common.csv = False,
    ):
        event_list = self.bbot_server.get_events()

        if json:
            for event in event_list:
                self.sys.stdout.buffer.write(self.orjson.dumps(event.model_dump()))
            return

        if csv:
            for line in self.json_to_csv(event_list, fieldnames=["name", "targets"]):
                self.sys.stdout.buffer.write(line)
            return

        table = self.Table()
        table.add_column("Type", style="bold dark_orange")
        table.add_column("Data", style="bold")
        for event in event_list:
            table.add_row(
                event.name,
                event.data if event.data else event.data_json,
            )
        self.stdout.print(table)
