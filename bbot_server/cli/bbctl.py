import sys
import asyncio
import logging
import traceback
from pathlib import Path
from omegaconf import OmegaConf
from rich.console import Console
from functools import cached_property

from bbot_server.errors import BBOTServerError
from bbot_server.cli.base import BaseBBCTL, Annotated, Option
from bbot_server.config import BBOT_SERVER_URL, BBOT_SERVER_CONFIG

# subcommand imports
from bbot_server.cli.agentctl import AgentCTL
from bbot_server.cli.assetctl import AssetCTL
from bbot_server.cli.scanctl import ScanCTL
from bbot_server.cli.serverctl import ServerCTL
from bbot_server.cli.eventctl import EventCTL
from bbot_server.cli.activityctl import ActivityCTL
from bbot_server.cli.targetctl import TargetCTL


class BBCTL(BaseBBCTL):
    """
    The root command for the BBCTL CLI
    """

    include = [AssetCTL, ScanCTL, TargetCTL, ServerCTL, AgentCTL, EventCTL, ActivityCTL]

    def __init__(self):
        super().__init__()
        self._bbot_server = None

    def main(
        self,
        server_url: Annotated[str, Option("--url", "-u", help="BBOT server URL", metavar="URL")] = BBOT_SERVER_URL,
        config: Annotated[str, Option("--config", "-c", help="Path to a config file", metavar="PATH")] = None,
        silent: Annotated[bool, Option("--silent", "-s", help="Suppress all stderr output")] = False,
        color: Annotated[
            bool, Option(f"--color/--no-color", "-cl/-ncl", help="Enable or disable color in the terminal")
        ] = True,
        debug: Annotated[bool, Option("--debug", "-d", help="Enable debug mode")] = False,
    ):
        self.silent = silent
        self.color = color
        self.debug = debug
        self.config_path = None
        if config:
            try:
                self.config_path = Path(config)
                config = OmegaConf.load(self.config_path)
                self._config = OmegaConf.merge(BBOT_SERVER_CONFIG, config)
            except Exception as e:
                raise BBOTServerError(f"Error loading config file {config}: {e}")
        else:
            self._config = BBOT_SERVER_CONFIG
        if self.debug:
            logging.getLogger().setLevel(logging.DEBUG)
        if server_url != BBOT_SERVER_URL:
            self._config.url = server_url
        self.server_url = self.config.url

        self._stdout = Console(file=sys.stdout, highlight=False, color_system=("auto" if self.color else None))
        self._stderr = Console(file=sys.stderr, highlight=False, color_system=("auto" if self.color else None))

    @cached_property
    def bbot_server(self):
        bbot_server_kwargs = {}
        if self.config:
            bbot_server_kwargs["config"] = self.config

        from bbot_server import BBOTServer

        bbot_server = BBOTServer(interface="http", url=self.server_url, synchronous=True, **bbot_server_kwargs)
        bbot_server.setup()
        return bbot_server


log = logging.getLogger("bbot_server.bbctl")


def main():
    bbctl = BBCTL()
    try:
        bbctl.typer()
    except BBOTServerError as e:
        _log = getattr(bbctl, "log", log)
        _log.error(str(e))
        _log.debug(traceback.format_exc())
        sys.exit(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        log.warning("Interrupted")
        sys.exit(2)
    finally:
        # only cleanup if bbot_server was instantiated
        if "bbot_server" in bbctl.__dict__:
            bbctl.bbot_server.cleanup()


if __name__ == "__main__":
    main()
