import os
import typer
import asyncio
from pathlib import Path
from subprocess import run
from omegaconf import OmegaConf
from contextlib import suppress

from bbot_server.cli import common
from bbot_server.config import BBOT_SERVER_CONFIG
from bbot_server.cli.base import BaseBBCTL, subcommand, Option, Annotated


class Server(BaseBBCTL):
    command = "server"
    help = "Start/stop BBOT server"
    epilog = "Start the main BBOT server via Docker Compose or individual components in standalone mode"

    def setup(self):
        self.docker_compose_dir = Path(__file__).parent.parent
        self.docker_compose_file = self.docker_compose_dir / "compose.yml"

    @subcommand(help="Print the current BBOT server config")
    def current_config(self):
        print(OmegaConf.to_yaml(self.bbot_server.config))

    @subcommand(help="Start BBOT server")
    def start(
        self,
        api_only: Annotated[
            bool, Option("--api-only", "-a", help="Only start the REST API, without Docker Compose")
        ] = False,
        watchdog_only: Annotated[
            bool, Option("--watchdog-only", "-w", help="Only start the watchdog, without Docker Compose")
        ] = False,
        listen: Annotated[str, Option("--listen", "-l", help="Listen address", metavar="IP_ADDRESS")] = "127.0.0.1",
        port: Annotated[int, Option("--port", "-p", help="Port to run the server on", metavar="PORT")] = 8807,
    ):
        if api_only:
            print("Starting BBOT server API")
            if self.root.config_path is not None:
                self.log.info(f"Using config file: {self.root.config_path}")
                os.environ["BBOT_SERVER_CONFIG"] = str(self.root.config_path)
            import uvicorn

            # TODO: increase workers after adding websocket channels
            uvicorn.run("bbot_server.api.app:server_app", host=listen, port=port, reload=True, workers=1)

        elif watchdog_only:
            print("Starting watchdog")

            async def run_watchdog():
                try:
                    from bbot_server import BBOTServer
                    from bbot_server.watchdog import BBOTWatchdog

                    bbot_server = BBOTServer(config=self.config)
                    await bbot_server.setup()

                    watchdog = BBOTWatchdog(bbot_server)
                    await watchdog.start()
                    print("Watchdog successfully started")

                    # sleep for infinity
                    event = asyncio.Event()
                    await event.wait()

                except KeyboardInterrupt:
                    with suppress(Exception):
                        await watchdog.stop()

            asyncio.run(run_watchdog())

        else:
            self.ensure_docker_compose()
            # docker compose command with env vars
            docker_compose_command = ["docker-compose", "up", "-d"]
            env = os.environ.copy()
            env["BBOT_HOST"] = "0.0.0.0"
            env["BBOT_PORT"] = str(port)
            run(docker_compose_command, check=False, cwd=self.docker_compose_dir, env=env)

    @subcommand(help="Stop BBOT server")
    def stop(self):
        self.ensure_docker_compose()
        run(["docker-compose", "down"], check=False, cwd=self.docker_compose_dir)

    def ensure_docker_compose(self):
        # make sure docker compose is installed
        commands = [["docker", "compose", "version"], ["docker-compose", "--version"]]
        for command in commands:
            try:
                if run(command, check=False):
                    return True
            except FileNotFoundError:
                continue
        raise typer.Exit("Docker compose is not installed. Please install docker compose and try again.")
