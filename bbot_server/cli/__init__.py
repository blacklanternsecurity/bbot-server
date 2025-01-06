import typer
import importlib
from pathlib import Path
from typing_extensions import Annotated

from bbot_server.cli import themes


bbctl = typer.Typer()


# global options
@bbctl.callback()
def args(
    bbot_url: Annotated[str, typer.Option("--url", "-u", help="BBOT server URL")] = "http://localhost:8807",
    silent: Annotated[bool, typer.Option("--silent", "-s", help="Suppress all stderr output")] = False,
    color: Annotated[
        bool, typer.Option(f"--color/--no-color", "-c/-nc", help="Enable or disable color in the terminal")
    ] = True,
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
 [bold dark_orange]|______/[/bold dark_orange]|_____/ \____/  |_|
"""
        stderr.print(ascii_art, highlight=False)


# load all the cli modules
cli_dir = Path(__file__).parent
for p in cli_dir.iterdir():
    # find every .py file in the cli directory
    if p.is_file() and p.suffix.lower() == ".py" and not p.stem.startswith("_"):
        # try importing it and look for typer.Typer objects
        module_name = p.stem
        full_namespace = f"bbot_server.cli.{module_name}"
        spec = importlib.util.spec_from_file_location(full_namespace, p)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for var_name in dir(module):
            if var_name.startswith("_"):
                continue
            var_value = getattr(module, var_name)
            # if a typer object is found, add it to bbctl
            if isinstance(var_value, typer.Typer):
                bbctl.add_typer(var_value, name=var_name)


def main():
    bbctl()


if __name__ == "__main__":
    main()
