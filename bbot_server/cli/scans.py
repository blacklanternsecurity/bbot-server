import typer
import uvloop
from rich.table import Table

from bbot_server import BBOTServer
from bbot_server.cli.utils import stdout
from bbot_server.cli.scan_editor import ScanEditor


scans = typer.Typer()


@scans.command(help="List preconfigured scans")
def list():
    async def get_assets():
        bbot_server = BBOTServer()
        await bbot_server.setup()

        scan_list = await bbot_server.get_scans()

        table = Table()
        table.add_column("Name", style="bold dark_orange")
        table.add_column("Targets")
        for scan in scan_list:
            table.add_row(scan.name, ", ".join(scan.target))

        stdout.print(table)

    uvloop.run(get_assets())


@scans.command(help="Create a new scan")
def create():
    scan, start_scan = ScanEditor().make_scan()
    if scan is None:
        return

    async def _create_scan():
        bbot_server = BBOTServer()
        await bbot_server.setup()
        await bbot_server.create_scan(scan)
        if start_scan:
            await bbot_server.start_scan(scan.name)

    uvloop.run(_create_scan())


async def _start_scan(name: str):
    bbot_server = BBOTServer()
    await bbot_server.setup()
    await bbot_server.start_scan(name)


@scans.command(help="Start a scan")
def start(name: str):
    uvloop.run(_start_scan(name))


@scans.command(help="List individual BBOT scan runs")
def runs():
    async def _list_runs():
        bbot_server = BBOTServer()
        await bbot_server.setup()
        scan_runs = await bbot_server.get_scan_runs()

        table = Table()
        table.add_column("status", style="bold white")
        table.add_column("Name", style="bold dark_orange")
        table.add_column("duration")
        table.add_column("started_at", style="bright_black")
        table.add_column("finished_at", style="bright_black")
        for scan_run in scan_runs:
            table.add_row(
                scan_run.status,
                scan_run.name,
                scan_run.duration,
                scan_run.started_at.strftime("%b %d, %Y %H:%M:%S"),
                scan_run.finished_at.strftime("%b %d, %Y %H:%M:%S") if scan_run.finished_at else "",
            )

        stdout.print(table)

    uvloop.run(_list_runs())
