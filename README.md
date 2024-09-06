# BBOT Server

[![Python Version](https://img.shields.io/badge/python-3.9+-FF8400)](https://www.python.org) [![License](https://img.shields.io/badge/license-GPLv3-FF8400.svg)](https://github.com/blacklanternsecurity/bbot/blob/dev/LICENSE) [![tests](https://github.com/blacklanternsecurity/bbot-io/actions/workflows/tests.yml/badge.svg)](https://github.com/blacklanternsecurity/bbot-io/actions/workflows/tests.yml) [![Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) [![Discord](https://img.shields.io/discord/859164869970362439)](https://discord.com/invite/PZqkgxu5SA)

BBOT Server is a database for your BBOT scan data. Deploy in a single command!

## Supported Backends

- [x] SQLite (default)
- [x] Postgres
- [x] REST Client

## Deployment

The main goal of BBOT Server is to make your scan data easy to view and manage and over time:

- Monitor changes in attack surface (new hosts, new vulnerabilities)

**I/O Modules** provide a uniform Python + REST API across many backends. They allow `bbot-server` to be deployed either as a lightweight standalone tool, or as a central hub for BBOT multiplayer ;)

Most importantly, it will provide a solid foundation for new BBOT projects going forward:
- Asset Inventory
- Interactive CLI (DIY ASM for hackers)
- BBOT Frontend (eventually?)

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

# visit REST API at http://127.0.0.1:8000/

# run bbot scan
bbot -t blacklanternsecurity.com -om http -c modules.http.url=http://localhost:8000/events/

# get subdomains
curl http://localhost:8000/subdomains
```

## Usage (Python)
```python
import asyncio

from bbot import Scanner
from bbot_io import BBOT_IO
from bbot_io.models import Event


async def main():
    # create SQLite database
    io = BBOT_IO("sqlite", database="./bbot.db")
    # or Postgres
    io = BBOT_IO("postgres", username="postgres", password="bbotislife", )

    # setup
    await io.setup()

    # fill database with BBOT data
    scan = Scanner("blacklanternsecurity.com")
    async for event in scan.async_start():
        pydantic_event = Event(**event.json())
        await io.create_event(pydantic_event)

    # get subdomains
    subdomains = await io.get_subdomains()
    print(subdomains)

    # get events
    events = await io.get_events()

    # clear database
    await io.drop_database()


if __name__ == "__main__":
    asyncio.run(main())
```

## Running Tests
```bash
# first, start postgres
docker run --rm -e POSTGRES_PASSWORD=bbotislife -p 5432:5432 postgres

# run tests
poetry run pytest
```

![bbot-server](https://github.com/user-attachments/assets/c68d3b81-0cb4-4721-9421-879c1b2b6d04)

### TODO

- [x] Basic tests
- [x] Github actions
- [ ] Codecov
- [ ] Full documentation
