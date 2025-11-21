import os
import sys
import asyncio
import logging
import traceback
from rich.console import Console
from functools import cached_property

from bbot_server.cli.base import BaseBBCTL, Annotated, Option
from bbot_server.errors import BBOTServerError, BBOTServerUnauthorizedError


class BBCTL(BaseBBCTL):
    """
    The root command for the BBCTL CLI
    """

    command = "bbctl"

    _invoke_without_command = True

    def __init__(self):
        super().__init__()
        self._bbot_server = None

    def main(
        self,
        server_url: Annotated[str, Option("--url", "-u", help="BBOT server URL", metavar="URL")] = None,
        config: Annotated[str, Option("--config", "-c", help="Path to a config file", metavar="PATH")] = None,
        silent: Annotated[bool, Option("--silent", "-s", help="Suppress all stderr output")] = False,
        color: Annotated[
            bool, Option(f"--color/--no-color", "-cl/-ncl", help="Enable or disable color in the terminal")
        ] = True,
        debug: Annotated[bool, Option("--debug", "-d", help="Enable debug mode")] = False,
        current_config: Annotated[bool, Option("--current-config", "-cc", help="Print the current config")] = False,
    ):
        self.silent = silent
        self.color = color
        self.debug = debug
        if config:
            os.environ["BBOT_SERVER_CONFIG"] = str(config)
            self.bbcfg.refresh()
        if self.debug:
            logging.getLogger().setLevel(logging.DEBUG)
        if server_url is not None and server_url != self.bbcfg.url:
            self._config.url = server_url
        self.server_url = self.config.url

        self._stdout = Console(file=sys.stdout, highlight=False, color_system=("auto" if self.color else None))
        self._stderr = Console(file=sys.stderr, highlight=False, color_system=("auto" if self.color else None))

        if current_config:
            self.print_yaml(self.config.model_dump())
            return

    @cached_property
    def bbot_server(self):
        from bbot_server import BBOTServer

        bbot_server = BBOTServer(interface="http", url=self.server_url, synchronous=True)
        bbot_server.setup()
        return bbot_server

    @property
    def _config(self):
        return self.bbcfg


log = logging.getLogger("bbot_server.bbctl")


def main():
    bbctl = BBCTL()
    _log = getattr(bbctl, "log", log)
    try:
        bbctl.typer()
    except BBOTServerUnauthorizedError as e:
        _log.error(f"Authentication failed: {e.detail}")
        sys.exit(1)
    except BBOTServerError as e:
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
