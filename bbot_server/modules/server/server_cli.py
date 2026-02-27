import os
import sys
import typer
import asyncio
import subprocess
from subprocess import run
from contextlib import suppress

from bbot_server.config import BBOT_SERVER_CONFIG as bbcfg, BBOT_SERVER_DIR
from bbot_server.cli.base import BaseBBCTL, subcommand, Option, Annotated


class ServerCTL(BaseBBCTL):
    command = "server"
    help = "Start/stop BBOT server via Docker Compose"
    short_help = "Start/stop BBOT server and manage API keys"
    attach_to = "bbctl"

    _invoke_without_command = True
    _no_args_is_help = True

    def setup(self):
        self._docker_command = None
        self.docker_compose_dir = BBOT_SERVER_DIR
        self.docker_compose_file = self.docker_compose_dir / "compose.yml"

    def main(
        self,
        dev: Annotated[
            bool, Option("--dev", "-d", help="Use dev compose file (builds from source, mounts code for live reload)")
        ] = False,
    ):
        if dev:
            self.docker_compose_dir = BBOT_SERVER_DIR.parent
            self.docker_compose_file = self.docker_compose_dir / "compose.yml"

    @subcommand(help="Start BBOT server")
    def start(
        self,
        api_only: Annotated[
            bool, Option("--api-only", "-a", help="Only start the REST API, without Docker Compose")
        ] = False,
        worker_only: Annotated[
            bool, Option("--worker-only", "-w", help="Only start the worker, without Docker Compose")
        ] = False,
        listen: Annotated[str, Option("--listen", "-l", help="Listen address", metavar="IP_ADDRESS")] = "127.0.0.1",
        port: Annotated[int, Option("--port", "-p", help="Port to run the server on", metavar="PORT")] = 8807,
        reload: Annotated[
            bool, Option("--reload", "-r", help="Reload the server when the code changes (for development)")
        ] = False,
        no_authentication: Annotated[
            bool, Option("--no-authentication", "-n", help="Disables authentication on the API (USE WITH CAUTION)")
        ] = False,
    ):
        if no_authentication:
            os.environ["BBOT_SERVER_AUTH_ENABLED"] = "false"

        if api_only:
            print("Starting BBOT server API")

            import uvicorn

            app = "bbot_server.api.app:server_app"

            # TODO: increase workers after adding websocket channels
            uvicorn.run(
                app,
                host=listen,
                port=port,
                reload=reload,
                reload_excludes=["mongodb"],
                workers=1,
            )

        elif worker_only:
            print("Starting worker")

            async def run_worker():
                try:
                    from bbot_server import BBOTServer
                    from bbot_server.worker import BBOTWorker

                    bbot_server = BBOTServer()
                    await bbot_server.setup()

                    worker = BBOTWorker(bbot_server)
                    await worker.start()
                    print("Worker successfully started")

                    # sleep for infinity
                    event = asyncio.Event()
                    await event.wait()

                except KeyboardInterrupt:
                    with suppress(Exception):
                        await worker.stop()

            asyncio.run(run_worker())

        else:
            # initialize the config if not already
            if not bbcfg.get_api_keys():
                self.log.info("First run detected. Adding a new API key...")
                self.root.children["server"].children["apikey"].setup()
                self.root.children["server"].children["apikey"].add()
            else:
                self.log.info("API keys already exist. Skipping API key creation.")

            # docker compose command with env vars
            env = os.environ.copy()
            env["BBOT_LISTEN_ADDRESS"] = listen
            env["BBOT_PORT"] = str(port)
            self._run_docker_compose(["up", "-d"], env=env)

    @subcommand(help="Stop BBOT server (via docker compose stop)")
    def stop(self):
        self._run_docker_compose(["stop"])

    @subcommand(help="Stop BBOT server (via docker compose down)")
    def down(self):
        self._run_docker_compose(["down"])

    @subcommand(help="List docker compose services")
    def status(self):
        self._run_docker_compose(["ps"])

    @subcommand(help="List docker compose logs")
    def logs(
        self,
        follow: Annotated[bool, Option("--follow", "-f", help="Follow the logs")] = False,
        tail: Annotated[int, Option("--tail", "-n", help="Number of lines to show from the end of the logs")] = None,
    ):
        command = ["logs"]
        if follow:
            command += ["--follow"]
            if tail is not None:
                command += ["--tail", str(tail)]
        self._run_docker_compose(command)

    @subcommand(help="Clear the database (drop Mongodb collections).")
    def cleardb(
        self,
        event_store: Annotated[bool, Option("--event-store", "-e", help="Clear the event store collections")] = False,
        asset_store: Annotated[bool, Option("--asset-store", "-a", help="Clear the asset store collections")] = False,
        user_store: Annotated[bool, Option("--user-store", "-u", help="Clear the user store collections")] = False,
    ):
        if not event_store and not asset_store and not user_store:
            raise self.BBOTServerError(f"Must specify at least one store to clear")

        stores_to_clear = []
        if event_store:
            stores_to_clear.append(("event store", self.config.event_store, "all BBOT scan events"))
        if asset_store:
            stores_to_clear.append(("asset store", self.config.asset_store, "all BBOT asset data"))
        if user_store:
            stores_to_clear.append(
                ("user store", self.config.user_store, "all BBOT user data, including presets and targets")
            )

        for store_name, store_config, data_desc in stores_to_clear:
            db_name = store_config.uri.split("/")[-1]
            prefix = store_config.collection_prefix
            if not db_name:
                raise self.BBOTServerError(f"{store_name.title()} database not found in config")
            response = input(
                f"Are you sure you want to clear the {store_name} (prefix: {prefix})? This will permanently delete {data_desc}! (y/N) "
            )
            if response.lower() != "y":
                raise self.BBOTServerError("Aborting")
            drop_eval = f"db.getCollectionNames().filter(c => c.startsWith('{prefix}')).forEach(c => db[c].drop())"
            self._run_docker_compose(["exec", "mongodb", "mongosh", "--eval", drop_eval, db_name])
            self.log.info(f"Successfully cleared {store_name} collections (prefix: {prefix})")

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

        docker_compose_command = self._docker_command + args
        self.log.info(f"Running docker compose command: {' '.join(docker_compose_command)}")
        return run(docker_compose_command, **kwargs)

    @subcommand(
        help="Run a command with docker compose",
        epilog="Example: bbctl server run-docker-compose exec server bash",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )
    def compose(self, args: list[str]):
        # we take sys.argv after "run-docker-compose"
        docker_compose_index = sys.argv.index("compose")
        docker_compose_args = sys.argv[docker_compose_index + 1 :]
        return self._run_docker_compose(docker_compose_args)
