# BBOT Server

[![Python Version](https://img.shields.io/badge/python-3.9+-FF8400)](https://www.python.org) [![License](https://img.shields.io/badge/license-GPLv3-FF8400.svg)](https://github.com/blacklanternsecurity/bbot/blob/dev/LICENSE) [![tests](https://github.com/blacklanternsecurity/bbot-io/actions/workflows/tests.yml/badge.svg)](https://github.com/blacklanternsecurity/bbot-io/actions/workflows/tests.yml) [![Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) [![Discord](https://img.shields.io/discord/859164869970362439)](https://discord.com/invite/PZqkgxu5SA)

BBOT Server is a database for your BBOT scan data. Deploy in a single command!

```bash
# install
pipx install git+https://github.com/blacklanternsecurity/bbot-server

# start bbot server
bbot-server -p 8080

# visit REST API at http://127.0.0.1:8000/

# run bbot scan
bbot -t blacklanternsecurity.com -om http -c modules.http.url=http://localhost:8000/events/

# get subdomains
curl http://localhost:8000/subdomains
```

## Supported Backends

- [x] SQLite (default)
- [x] Postgres
- [x] REST Client

## How it works

BBOT server has several layers of abstraction which make it very versatile:

### **User** --> **Interfaces** --> **Applets** --> **Backends**

---

### 1. Interfaces (`bbot_io/interfaces/*.py`)

Interfaces let you interact transparently with the BBOT server via its python API, regardless of whether you're on the same system. This will useful in building future projects, such as an interactive command-line interface, because it allows multiple clients to connect at the same time (BBOT multiplayer!).

Right now there are only two interfaces: `local` and `http`. In the future we might add more high-performance protocols like ZeroMQ.

### 2. Applets (`bbot_io/applets/*.py`)

Applets are where the core business logic lives. They make it easy to add new functionality, while keeping BBOT server small and lightweight.

Each applet (e.g. `Events`, `Scans`, or `Subdomains`) has a small collection of python functions (e.g. `get_subdomains()`), which double as HTTP endpoints. Methods from all applets can be accessed directly from the `BBOT_IO` interface.

Each applet typically has its own database model (i.e. its own SQL table), but can also access other applets if needed. For example, `io.delete_scan()` will remove a scan from the `scan` table, but also delete all its events from the `event` table. 

### 3. Backends (`bbot_io/backends/*.py`)

Backends abstract the database. This enables you to spin up quickly with `sqlite`, or use `postgres` for bigger datasets.

## Usage (Python)
```python
import asyncio

from bbot import Scanner
from bbot_io import BBOT_IO
from bbot_io.models import Event


async def main():
    # local SQLite database
    io = BBOT_IO("sqlite", database="./bbot.db")
    # or Postgres
    io = BBOT_IO("postgres", host="localhost", username="postgres", password="bbotislife")
    # or a BBOT server already running somewhere else
    io = BBOT_IO("http", url="http://bbot.server")

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
