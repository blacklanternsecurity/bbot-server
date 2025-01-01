import typer
import orjson
import uvloop
from rich.table import Table
from datetime import datetime, timezone
from typing_extensions import Annotated

from .utils import stdout
from bbot_server import BBOTServer


assets = typer.Typer()


# TODO: replace this with bbot_server.tail_assets()
async def _tail(json: bool = False):
    from bbot_server.message_queue.message_queue import MessageQueue

    message_queue = MessageQueue()
    await message_queue.setup()
    async for asset_activity in message_queue.asset_tail():
        if json:
            print(orjson.dumps(asset_activity))
        else:
            timestamp = asset_activity["timestamp"]
            description = asset_activity["description_colored"]
            timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%b %d %Y %H:%M:%S")
            stdout.print(f"[[bright_black]{timestamp}[/bright_black]] - [bold]{description}[/bold]", highlight=False)


async def get_assets():
    bbot_server = BBOTServer()
    await bbot_server.setup()

    assets = await bbot_server.assets.get_assets()

    table = Table()
    table.add_column("Asset", style="bold dark_orange")
    table.add_column("Extra fields")
    for asset in assets:
        table.add_row(asset.host, str(len(asset.extra_fields)))

    stdout.print(table)


@assets.command(help="List assets")
def list():
    uvloop.run(get_assets())


@assets.command(help="Watch for new asset activity")
def tail(json: Annotated[bool, typer.Option("--json", "-j", help="Output asset activity as raw JSON")] = False):
    uvloop.run(_tail(json))
