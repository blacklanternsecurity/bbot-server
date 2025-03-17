import logging
from omegaconf import OmegaConf

from bbot_server.errors import BBOTServerError
from bbot_server.config import BBOT_SERVER_CONFIG
from bbot_server.cli.base import BaseBBCTL, Annotated, Option

# subcommand imports
from bbot_server.cli.scans import Scans
from bbot_server.cli.server import Server


class BBCTL(BaseBBCTL):
    """
    The root command for the BBCTL CLI
    """

    include = [Scans, Server]

    def __init__(self):
        super().__init__()
        self._bbot_server = None

    def main(
        self,
        bbot_url: Annotated[
            str, Option("--url", "-u", help="BBOT server URL", metavar="URL")
        ] = BBOT_SERVER_CONFIG.url,
        config: Annotated[str, Option("--config", "-c", help="Path to a config file", metavar="PATH")] = None,
        silent: Annotated[bool, Option("--silent", "-s", help="Suppress all stderr output")] = False,
        color: Annotated[
            bool, Option(f"--color/--no-color", "-cl/-ncl", help="Enable or disable color in the terminal")
        ] = True,
    ):
        self.bbot_url = bbot_url
        self.silent = silent
        self.color = color
        self._config = config

    @property
    def bbot_server(self):
        if self._bbot_server is None:
            bbot_server_kwargs = {}
            if self.config:
                bbot_server_kwargs["config"] = self.config

            from bbot_server import BBOTServer

            self._bbot_server = BBOTServer(interface="http", url=self.bbot_url, synchronous=True, **bbot_server_kwargs)
            self._bbot_server.setup()
        return self._bbot_server


log = logging.getLogger("bbot.server.bbctl")


def main():
    bbctl = BBCTL()
    try:
        bbctl.typer()
    except BBOTServerError as e:
        log.error(str(e))
