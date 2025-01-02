import typer
import uvloop
from rich.table import Table

from bbot_server import BBOTServer
from bbot_server.cli.utils import stdout

targets = typer.Typer()


@targets.command(help="List targets")
def list():
    async def get_assets():
        bbot_server = BBOTServer()
        await bbot_server.setup()

        target_list = await bbot_server.get_targets()

        table = Table()
        table.add_column("Name", style="bold dark_orange")
        table.add_column("Whitelist")
        for target in target_list:
            table.add_row(target.name, ", ".join(target.whitelist))

        stdout.print(table)

    uvloop.run(get_assets())
