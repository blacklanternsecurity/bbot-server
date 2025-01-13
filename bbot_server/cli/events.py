import typer
import orjson
import uvloop
import csv as csvlib
from typing import Annotated
from rich.table import Table
from datetime import datetime, timezone

from bbot_server import BBOTServer
from bbot_server.cli.utils import stdout


events = typer.Typer()


@events.command(help="List events")
def list(
    json: Annotated[bool, typer.Option("--json", "-j", help="Output asset activity as raw JSON")] = False,
    csv: Annotated[bool, typer.Option("--csv", "-c", help="Output events as CSV")] = False,
):
    async def get_events():
        bbot_server = BBOTServer()
        await bbot_server.setup()

        event_list = await bbot_server.get_events()

        if json:
            for event in event_list:
                print(orjson.dumps(event.model_dump()).decode())
        elif csv:
            output = csvlib.StringIO()
            csv_writer = csvlib.writer(output)
            csv_writer.writerow(["Timestamp", "Type", "Data", "Tags"])
            for event in event_list:
                timestamp = datetime.fromtimestamp(event.timestamp, tz=timezone.utc).strftime("%b %d, %Y %H:%M:%S")
                csv_writer.writerow([timestamp, event.type, str(event.data), ", ".join(sorted(event.tags))])
            print(output.getvalue())
        else:
            table = Table()
            table.add_column("Timestamp", style="bright_black")
            table.add_column("Type", style="dark_orange")
            table.add_column("Data", style="bold white")
            table.add_column("Tags")
            for event in event_list:
                timestamp = datetime.fromtimestamp(event.timestamp, tz=timezone.utc).strftime("%b %d, %Y %H:%M:%S")
                table.add_row(timestamp, event.type, str(event.data), ", ".join(sorted(event.tags)))

            stdout.print(table)

    uvloop.run(get_events())


@events.command(help="Watch for new events")
def tail(
    json: Annotated[bool, typer.Option("--json", "-j", help="Output events as raw JSON")] = False,
):
    # TODO: replace this with bbot_server.tail_assets()
    async def _tail():
        from bbot_server.message_queue.message_queue import MessageQueue

        message_queue = MessageQueue()
        await message_queue.setup()
        async for event in message_queue.event_tail():
            if json:
                print(orjson.dumps(event).decode())
            else:
                timestamp = event["timestamp"]
                timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%b %d %Y %H:%M:%S")
                event_type = event["type"]
                data = event.get("data", event.get("data_json", ""))
                if isinstance(data, dict):
                    data = orjson.dumps(data)
                stdout.print(f"[[bright_black]{timestamp}[/bright_black]] - [bold]{event_type}[/bold] - {data}")

    uvloop.run(_tail())
