# BBOT I/O

[![Python Version](https://img.shields.io/badge/python-3.9+-FF8400)](https://www.python.org) [![License](https://img.shields.io/badge/license-GPLv3-FF8400.svg)](https://github.com/blacklanternsecurity/bbot/blob/dev/LICENSE) [![Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) [![Discord](https://img.shields.io/discord/859164869970362439)](https://discord.com/invite/PZqkgxu5SA)

BBOT I/O is a (WIP) database for your BBOT scan data.

![bbot-server](https://github.com/blacklanternsecurity/bbot/assets/20261699/49bd62a9-b862-44cb-aa36-1c347378a734)

## I/O Modules

The main goal of BBOT I/O is to make BBOT scan data easy to view and manage.

**I/O Modules** provide a uniform Python + REST API across many backends. They allow `bbot-server` to be deployed either as a lightweight standalone tool, or as a central hub for BBOT multiplayer ;)

Most importantly, I/O modules will provide a solid foundation for new projects built on top of BBOT:
- Asset Inventory
- Interactive CLI (DIY ASM for hackers)
- BBOT Frontend (eventually?)

## BBOT Server

`bbot-server` is a tiny REST API built on top of BBOT I/O. It will evolve with these projects, and may end up being split off into its own project.

## Backends

Backends are modular and easy to add!

- [x] SQLite (default)
- [x] MongoDB
- [ ] REST Client
- [ ] Postgres
- [ ] Neo4j

### Other TODOs

- [x] Basic tests
- [ ] Github actions
- [ ] Codecov
- [ ] Full documentation

## Installation

```bash
# pipx
pipx install git+https://github.com/blacklanternsecurity/bbot-server

# poetry
git clone git@github.com:blacklanternsecurity/bbot-server.git && cd bbot-server
poetry install
```

## Usage (CLI)

```bash
# start bbot server
bbot-server -p 8000

# visit REST API at http://127.0.0.1:8000/docs

# run bbot scan
bbot -t blacklanternsecurity.com -om websocket -c modules.websocket.url=ws://localhost:8000/ws

# get subdomains
curl http://localhost:8000/subdomains
```

## Usage (Python)
```python
import asyncio

from bbot import Scanner
from bbot_io.modules import IO
from bbot_io.models import Event


async def main():
    # create BBOT I/O
    io = IO("sqlite", db_file="./bbot.db")

    # fill database with BBOT data
    scan = Scanner("blacklanternsecurity.com")
    async for event in scan.async_start():
        pydantic_event = Event(**event.json())
        await io.insert_event(pydantic_event)

    # get subdomains
    for subdomain in await io.get_subdomains():
        print(subdomain)

    # get events
    for event in await io.get_events():
        print(event)

    # clear database
    await io.drop_database()


if __name__ == "__main__":
    asyncio.run(main())
```

## Running Tests
```bash
# first, start mongodb
docker run --rm -it -p 27017:27017 mongo

# run tests
poetry run pytest
```
