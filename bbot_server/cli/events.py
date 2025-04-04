import typer
from pathlib import Path
from typing import Annotated

from bbot.models.pydantic import Event

from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand


class Events(BaseBBCTL):
    command = "events"
    help = "Query, tail, or ingest BBOT events"
    epilog = "Query, tail, or ingest BBOT events"

    @subcommand(help="List BBOT events")
    def list(
        self,
        json: common.json = False,
        csv: common.csv = False,
    ):
        event_list = self.bbot_server.get_events()

        if json:
            for event in event_list:
                self.sys.stdout.buffer.write(self.orjson.dumps(event.model_dump()) + b"\n")
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

    @subcommand(
        help="Ingest BBOT scan events from a file or stdin. Events must be valid JSON.",
        epilog="Example: cat output.json | bbctl events ingest",
    )
    def ingest(
        self,
        file: Annotated[
            Path, typer.Option("--file", "-f", help="file to ingest (don't specify or use '-' to read from stdin)")
        ] = None,
    ):
        def event_generator():
            if file in (None, Path("-")):
                stream = self.sys.stdin
            else:
                stream = open(file, "r")
            for line in stream:
                try:
                    json_event = self.orjson.loads(line)
                    event = Event(**json_event)
                    yield event
                except Exception as e:
                    self.log.warning(f"Invalid event JSON: {line}: {e}")

        for count, event in enumerate(event_generator()):
            self.bbot_server.insert_event(event)
            if count and count % 10 == 0:
                self.log.info(f"Ingested {count:,} events")
