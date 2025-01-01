import typer
from typing_extensions import Annotated


bbctl = typer.Typer()

# set default rich style
typer.rich_utils.STYLE_OPTION = "bold dark_orange"
typer.rich_utils.STYLE_SWITCH = "bold dark_orange"
typer.rich_utils.STYLE_USAGE = "bright_white"
typer.rich_utils.STYLE_METAVAR = "bold yellow"
typer.rich_utils.STYLE_OPTION_ENVVAR = "dim yellow"


# global options
@bbctl.callback()
def args(
    bbot_url: Annotated[str, typer.Option("--url", "-u", help="BBOT server URL")] = "http://localhost:8807",
    silent: Annotated[bool, typer.Option("--silent", "-s", help="Silent mode")] = False,
    color: Annotated[bool, typer.Option("--color", "-c", help="Color mode")] = True,
):
    from .utils import stderr, BBCTL_GLOBALS

    BBCTL_GLOBALS.silent = silent
    BBCTL_GLOBALS.color = color

    if not silent:
        ascii_art = r""" [bold dark_orange] ______ [/bold dark_orange] _____   ____ _______
 [bold dark_orange]|  ___ \\[/bold dark_orange]|  __ \ / __ \__   __|
 [bold dark_orange]| |___) [/bold dark_orange]| |__) | |  | | | |
 [bold dark_orange]|  ___ <[/bold dark_orange]|  __ <| |  | | | |
 [bold dark_orange]| |___) [/bold dark_orange]| |__) | |__| | | |
 [bold dark_orange]|______/[/bold dark_orange]|_____/ \____/  |_|"""
        stderr.print(ascii_art, highlight=False)


# server command
from .server import server

bbctl.add_typer(server, name="server")


# activity command
from .assets import assets

bbctl.add_typer(assets, name="assets")


def main():
    bbctl()


if __name__ == "__main__":
    main()
