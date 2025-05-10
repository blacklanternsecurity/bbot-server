import os
import sys
import typer
import asyncio
import subprocess
from pathlib import Path
from subprocess import run
from contextlib import suppress

from bbot_server import BBOT_SERVER_PROJECT_ROOT
from bbot_server.cli.base import BaseBBCTL, subcommand, Option, Annotated


class ServerCTL(BaseBBCTL):
    command = "server"
    help = "Start/stop BBOT server"
    short_help = "Start the main BBOT server via Docker Compose or individual components in standalone mode. These commands must be run from the server machine."

    def setup(self):
        self._docker_command = None
        self.docker_compose_dir = Path(__file__).parent.parent
        self.docker_compose_file = self.docker_compose_dir / "compose.yml"

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
        reload: Annotated[
            bool, Option("--reload", "-r", help="Reload the server when the code changes (for development)")
        ] = False,
    ):
        if api_only:
            print("Starting BBOT server API")
            if self.root.config_path is not None:
                self.log.info(f"Using config file: {self.root.config_path}")
                os.environ["BBOT_SERVER_CONFIG"] = str(self.root.config_path)
            import uvicorn

            if reload:
                app = "bbot_server.api.app:server_app"
            else:
                from functools import partial
                from bbot_server.api import make_server_app

                app = partial(make_server_app, config=self.config)

            # TODO: increase workers after adding websocket channels
            uvicorn.run(
                app,
                host=listen,
                port=port,
                reload=reload,
                reload_excludes=[str(BBOT_SERVER_PROJECT_ROOT / "mongodb")],
                workers=1,
            )

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
            # docker compose command with env vars
            env = os.environ.copy()
            env["BBOT_HOST"] = "0.0.0.0"
            env["BBOT_PORT"] = str(port)
            self._run_docker_compose(["up", "-d"], env=env)

    @subcommand(help="Stop BBOT server (via docker compose stop)")
    def stop(self):
        self._run_docker_compose(["stop"])

    @subcommand(help="Stop BBOT server (via docker compose down)")
    def down(self):
        self._run_docker_compose(["down"])

    @subcommand(help="List docker compose services")
    def ps(self):
        self._run_docker_compose(["ps"])

    @subcommand(help="List docker compose logs")
    def logs(
        self,
        follow: Annotated[bool, Option("--follow", "-f", help="Follow the logs")] = False,
        tail: Annotated[int, Option("--tail", "-n", help="Number of lines to show from the end of the logs")] = 100,
    ):
        self._run_docker_compose(["logs", "--tail", str(tail), "--follow" if follow else ""])

    @subcommand(help="Clear the database (drop Mongodb collections).")
    def cleardb(
        self,
        event_store: Annotated[bool, Option("--event-store", "-e", help="Clear the event store database")] = False,
        asset_store: Annotated[bool, Option("--asset-store", "-a", help="Clear the asset store database")] = False,
        user_store: Annotated[bool, Option("--user-store", "-u", help="Clear the user store database")] = False,
    ):
        if not event_store and not asset_store and not user_store:
            raise self.BBOTServerError(f"Must specify at least one database to clear")

        if event_store:
            event_store_db = self.config.get("event_store", {}).get("uri", "").split("/")[-1]
            if not event_store_db:
                raise self.BBOTServerError("Event store database not found in config")
            response = input(
                f"Are you sure you want to clear the event store database: {event_store_db}? This will permanently delete all BBOT scan events! (y/N) "
            )
            if response.lower() != "y":
                raise self.BBOTServerError("Aborting")

            self._run_docker_compose(["exec", "mongodb", "mongosh", "--eval", "db.dropDatabase()", event_store_db])
            self.log.info(f"Successfully cleared event store database: {event_store_db}")

        if asset_store:
            asset_store_db = self.config.get("asset_store", {}).get("uri", "").split("/")[-1]
            if not asset_store_db:
                raise self.BBOTServerError("Asset store database not found in config")
            response = input(
                f"Are you sure you want to clear the asset store database: {asset_store_db}? This will permanently delete all BBOT asset data! (y/N) "
            )
            if response.lower() != "y":
                raise self.BBOTServerError("Aborting")
            self._run_docker_compose(["exec", "mongodb", "mongosh", "--eval", "db.dropDatabase()", asset_store_db])
            self.log.info(f"Successfully cleared asset store database: {asset_store_db}")

        if user_store:
            user_store_db = self.config.get("user_store", {}).get("uri", "").split("/")[-1]
            if not user_store_db:
                raise self.BBOTServerError("User store database not found in config")
            response = input(
                f"Are you sure you want to clear the user store database: {user_store_db}? This will permanently delete all BBOT user data, including presets and targets! (y/N) "
            )
            if response.lower() != "y":
                raise self.BBOTServerError("Aborting")
            self._run_docker_compose(["exec", "mongodb", "mongosh", "--eval", "db.dropDatabase()", user_store_db])
            self.log.info(f"Successfully cleared user store database: {user_store_db}")

    def _run_docker_compose(self, args, **kwargs):
        kwargs["cwd"] = self.docker_compose_dir
        if self._docker_command is None:
            try:
                run(["docker", "compose", "version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self._docker_command = ["docker", "compose"]
            except (FileNotFoundError, subprocess.CalledProcessError):
                try:
                    run(
                        ["docker-compose", "--version"],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    self._docker_command = ["docker-compose"]
                except (FileNotFoundError, subprocess.CalledProcessError):
                    raise typer.Exit("Docker compose is not installed. Please install docker compose and try again.")

        return run(self._docker_command + args, **kwargs)

    @subcommand(
        help="Run a command with docker compose",
        epilog="Example: `bbctl server compose ps` or `bbctl server compose exec server bash`",
    )
    def compose(self, args: list[str]):
        # we take sys.argv after "run-docker-compose"
        docker_compose_index = sys.argv.index("compose")
        docker_compose_args = sys.argv[docker_compose_index + 1 :]
        return self._run_docker_compose(docker_compose_args)
