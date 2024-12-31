import typer
from typing_extensions import Annotated

bbot_server = None


bbctl = typer.Typer()


# global options
@bbctl.callback()
def args(bbot_url: Annotated[str, typer.Option("--url", "-u", help="BBOT server URL")] = "http://localhost:8807"):
    global bbot_server
    from bbot_server.interfaces import BBOTServer

    bbot_server = BBOTServer(interface="http", url=bbot_url)


# server command
from .server import server

bbctl.add_typer(server, name="server")


# activity command
from .activity import activity

bbctl.add_typer(activity, name="activity")


def main():
    bbctl()


if __name__ == "__main__":
    main()
