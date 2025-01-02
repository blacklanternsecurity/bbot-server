import typer
import orjson
import uvloop
from rich.table import Table
from datetime import datetime, timezone
from typing_extensions import Annotated

from bbot_server import BBOTServer
from bbot_server.cli.utils import stdout


assets = typer.Typer()


@assets.command(help="List assets")
def list():
    async def get_assets():
        bbot_server = BBOTServer()
        await bbot_server.setup()

        asset_list = await bbot_server.get_assets()

        table = Table()
        table.add_column("Asset", style="bold dark_orange")
        table.add_column("Extra fields")
        for asset in asset_list:
            table.add_row(asset.host, str(len(asset.fields)))

        stdout.print(table)

    uvloop.run(get_assets())


@assets.command(help="Watch for new asset activity")
def tail(
    json: Annotated[bool, typer.Option("--json", "-j", help="Output asset activity as raw JSON")] = False,
    lines: Annotated[int, typer.Option("--lines", "-n", help="Number of previous asset activities to show")] = 10,
):
    # TODO: replace this with bbot_server.tail_assets()
    async def _tail():
        from bbot_server.message_queue.message_queue import MessageQueue

        message_queue = MessageQueue()
        await message_queue.setup()
        async for asset_activity in message_queue.asset_tail(lines=lines):
            if json:
                print(orjson.dumps(asset_activity).decode())
            else:
                timestamp = asset_activity["timestamp"]
                description = asset_activity["description_colored"]
                timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%b %d %Y %H:%M:%S")
                stdout.print(
                    f"[[bright_black]{timestamp}[/bright_black]] - [bold]{description}[/bold]", highlight=False
                )

    uvloop.run(_tail())
