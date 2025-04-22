import typer
from pathlib import Path
from typing import Annotated

from bbot.models.pydantic import Event
from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand


class EventCTL(BaseBBCTL):
    command = "event"
    help = "Query, tail, or ingest BBOT events"
    short_help = "Query, tail, or ingest BBOT events"

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
        table.add_column("Timestamp", style=self.DARK_COLOR)
        table.add_column("Type", style=self.COLOR)
        table.add_column("Data", style="bold")
        table.add_column("Scope")
        table.add_column("Tags")
        for event in event_list:
            event_data = event.data if event.data else self.orjson.dumps(event.data_json).decode()
            event_data = event_data[:100] + "..." if len(event_data) > 100 else event_data
            table.add_row(
                self.timestamp_to_human(event.timestamp),
                event.type,
                event_data,
                event.scope_description,
                ", ".join(sorted(event.tags)),
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

    @subcommand(help="Tail BBOT events")
    def tail(
        self,
        n: int = 10,
        json: common.json = False,
    ):
        for e in self.bbot_server.tail_events(n=n):
            if json:
                self.sys.stdout.buffer.write(self.orjson.dumps(e.model_dump()) + b"\n")
                continue

            timestamp = self.timestamp_to_human(e.timestamp)
            timestamp = f"[[{self.DARK_COLOR}]{timestamp}[/{self.DARK_COLOR}]]"
            event_type = f"[{self.COLOR}]{e.type}[/{self.COLOR}]"
            event_data = e.data if e.data else self.orjson.dumps(e.data_json).decode()
            event_data = event_data[:100] + "..." if len(event_data) > 100 else event_data
            event_data = f"[bold]{event_data}[/bold]"
            event_tags = ", ".join(sorted(e.tags))
            event_tags = f"[{self.DARK_COLOR}]{event_tags}[/{self.DARK_COLOR}]"
            self.stdout.print(f"{timestamp} {event_type}: {event_data} ({event_tags})")
