import os
import typer
from pathlib import Path
from subprocess import run
from typing import Annotated


server = typer.Typer()


docker_compose_dir = Path(__file__).parent.parent
docker_compose_file = docker_compose_dir / "docker-compose-dev.yml"


def bbot_server():
    import uvicorn

    port = int(os.environ.get("BBOT_PORT", 8807))
    host = os.environ.get("BBOT_HOST", "127.0.0.1")
    auto_reload = bool(os.environ.get("BBOT_AUTO_RELOAD", False))
    uvicorn.run("bbot_server.api:server_app", host=host, port=port, reload=auto_reload, log_level="debug")


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


@server.command(help="Start BBOT server")
def start(
    port: Annotated[int, typer.Option("--port", "-p", help="Port to run the server on")] = 8807,
    listen: Annotated[str, typer.Option("--listen", "-l", help="Listen address")] = "127.0.0.1",
    auto_reload: Annotated[bool, typer.Option("--auto-reload", "-r", help="Auto reload after code changes")] = False,
):
    ensure_docker_compose()
    # docker compose command with env vars
    docker_compose_command = ["docker-compose", "up", "-d"]
    env = os.environ.copy()
    env["BBOT_PORT"] = str(port)
    env["BBOT_HOST"] = listen
    env["BBOT_AUTO_RELOAD"] = str(auto_reload)
    run(docker_compose_command, check=False, cwd=docker_compose_dir, env=env)


@server.command(help="Stop the BBOT server")
def stop():
    ensure_docker_compose()
    run(["docker-compose", "down"], check=False)


if __name__ == "__main__":
    # for running inside docker compose
    os.environ["BBOT_PORT"] = "8807"
    os.environ["BBOT_HOST"] = "0.0.0.0"
    os.environ["BBOT_AUTO_RELOAD"] = "True"
    bbot_server()
