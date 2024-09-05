# BBOT I/O

[![Python Version](https://img.shields.io/badge/python-3.9+-FF8400)](https://www.python.org) [![License](https://img.shields.io/badge/license-GPLv3-FF8400.svg)](https://github.com/blacklanternsecurity/bbot/blob/dev/LICENSE) [![Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) [![Discord](https://img.shields.io/discord/859164869970362439)](https://discord.com/invite/PZqkgxu5SA)

BBOT I/O is a (WIP) database for your BBOT scan data.

![bbot-server](https://github.com/blacklanternsecurity/bbot/assets/20261699/49bd62a9-b862-44cb-aa36-1c347378a734)

## I/O Modules

The main goal of BBOT I/O is to make BBOT scan data easy to view and manage and over time.

**I/O Modules** provide a uniform Python + REST API across many backends. They allow `bbot-server` to be deployed either as a lightweight standalone tool, or as a central hub for BBOT multiplayer ;)

Most importantly, I/O modules will provide a solid foundation for new BBOT projects going forward:
- Asset Inventory
- Interactive CLI (DIY ASM for hackers)
- BBOT Frontend (eventually?)

## BBOT Server

`bbot-server` is a tiny REST API built on top of BBOT I/O. It will evolve over time, and may eventually become its own project.

## Backends

Backends are modular and easy to add!

- [x] SQLite (default)
- [ ] MongoDB
- [ ] REST Client
- [x] Postgres
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
    # create SQLite database
    io = IO("sqlite", database="./bbot.db")
    # or MongoDB
    io = IO("mongo", uri="mongodb://localhost:27017")

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

## Thoughts on Libraries

Choosing the right underlying libraries for this project is really important. It's also a difficult decision, especially because of the way this library needs to expose both a *python* API and and *web* API.

The goal of this project is to a have a single interface to the BBOT database, with friendly functions like `get_subdomains()` and `delete_scan()`:

```python
io = BBOT_IO(backend="sqlite")
io.get_subdomains()
io.delete_scan(scan_id)
```

With matching REST API endpoints:

```bash
curl http://bbot.server/get_subdomains
curl http://bbot.server/delete_scan?scan_id=scan_id
```

These matching endpoints will allow us to make an *HTTP client* that behaves exactly like the *python API*, so they can be used interchangeably.

We need to support multiple backends, so we can scale hugely if needed. We also need the ability to deploy a lightweight, standalone version, for personal setups.
