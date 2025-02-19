import os
import typer
import asyncio
from pathlib import Path
from subprocess import run
from typing import Annotated


server = typer.Typer()


docker_compose_dir = Path(__file__).parent.parent
docker_compose_file = docker_compose_dir / "docker-compose-dev.yml"


def ensure_docker_compose():
    # make sure docker compose is installed
    commands = [["docker-compose", "--version"], ["docker", "compose", "version"]]
    for command in commands:
        try:
            if run(command, check=False):
                return True
        except FileNotFoundError:
            continue
    raise typer.Exit("Docker compose is not installed. Please install docker compose and try again.")


@server.command(help="Start BBOT server and its supporting services using ")
def start(
    port: Annotated[int, typer.Option("--port", "-p", help="Port to run the server on")] = 8807,
    listen: Annotated[str, typer.Option("--listen", "-l", help="Listen address")] = "127.0.0.1",
    auto_reload: Annotated[bool, typer.Option("--auto-reload", "-r", help="Auto reload after code changes")] = False,
    http_only: Annotated[
        bool, typer.Option("--api-only", "-h", help="Start the HTTP server directly, without docker compose")
    ] = False,
    watchdog_only: Annotated[
        bool, typer.Option("--watchdog-only", "-w", help="Start the watchdog only, without docker compose")
    ] = False,
):
    auto_reload = auto_reload or bool(os.environ.get("BBOT_AUTO_RELOAD", False))

    if http_only:
        import uvicorn

        uvicorn.run("bbot_server.api.app:server_app", host=listen, port=port, reload=auto_reload)
    elif watchdog_only:
        print("Starting watchdog")

        async def run_watchdog():
            try:
                from bbot_server import BBOTServer
                from bbot_server.watchdog.worker import WatchdogWorker

                bbot_server = BBOTServer()
                await bbot_server.setup()

                watchdog = WatchdogWorker(bbot_server)
                await watchdog.start()
                print("Watchdog successfully started")

                # sleep for infinity
                event = asyncio.Event()
                await event.wait()

            except KeyboardInterrupt:
                await watchdog.stop()

        import uvloop

        uvloop.run(run_watchdog())

    else:
        ensure_docker_compose()
        # docker compose command with env vars
        docker_compose_command = ["docker-compose", "up", "-d"]
        env = os.environ.copy()
        env["BBOT_HOST"] = "0.0.0.0"
        env["BBOT_PORT"] = str(port)
        env["BBOT_AUTO_RELOAD"] = str(auto_reload)
        run(docker_compose_command, check=False, cwd=docker_compose_dir, env=env)


@server.command(help="Stop the BBOT server")
def stop():
    ensure_docker_compose()
    run(["docker-compose", "down"], check=False)
