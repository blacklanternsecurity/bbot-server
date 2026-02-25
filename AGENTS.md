# AGENTS.md

## Project Summary

BBOT Server is a database and multiplayer hub for [BBOT](https://github.com/blacklanternsecurity/bbot), an open-source security reconnaissance tool. It ingests BBOT scan events, tracks assets over time, detects changes, and exposes everything through multiple interfaces: a REST API (FastAPI), a Python SDK, a CLI (`bbctl`), and a Terminal UI (Textual).

Key capabilities:
- Ingest scan events in real-time or after the fact
- Track assets with detailed history and change detection
- Multi-user collaboration via shared server
- Query and export assets, findings, technologies, open ports, DNS, etc.
- AI interaction via MCP (Model Context Protocol)

### Architecture

The server is built on FastAPI with PostgreSQL for storage and Redis for message queuing. The codebase is organized into **modules**, each owning its own API endpoints, CLI commands, and data models. Modules are discovered and loaded dynamically at startup.

```
bbot_server/
├── api/            # FastAPI app setup
├── cli/            # bbctl CLI (Typer/Click)
├── db/             # PostgreSQL connection and table definitions
├── models/         # Base Pydantic/SQLModel classes
├── interfaces/     # Python (direct DB) and HTTP (REST client) interfaces
├── modules/        # Feature modules (assets, events, findings, scans, etc.)
│   └── <module>/
│       ├── <module>_api.py      # FastAPI applet (BaseApplet)
│       ├── <module>_cli.py      # CLI commands (BaseBBCTL)
│       └── <module>_models.py   # Data models
├── store/          # Data store abstraction
├── event_store/    # Event storage
├── message_queue/  # Redis-based task queue
├── applets/        # Async task runners
└── watchdog/       # Asset change detection
```

## Tooling

### uv

We use [uv](https://docs.astral.sh/uv/) for dependency management and virtual environments.

```bash
# Install dependencies
uv sync

# Run any command in the venv
uv run <command>
```

Dependencies are declared in `pyproject.toml` and locked in `uv.lock`. BBOT itself is pulled from the `3.0` branch on GitHub (not PyPI).

### Ruff

We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting. Configuration lives in `pyproject.toml`:

- Line length: 119
- Rules: `E` (PEP 8) and `F` (PyFlakes)
- Target: Python 3.10+

```bash
# Lint
uv run ruff check

# Format check
uv run ruff format --check

# Auto-fix
uv run ruff check --fix
uv run ruff format
```

### Running Tests

Tests use pytest with async support. Before running, start the backing services:

```bash
docker run --rm -p 5432:5432 -e POSTGRES_DB=test_bbot_server -e POSTGRES_USER=bbot -e POSTGRES_PASSWORD=bbot postgres:16
docker run --rm -p 6379:6379 redis
```

Then run:

```bash
# All tests
uv run pytest

# Specific test
uv run pytest -k test_applet_scans

# With coverage
uv run pytest --cov=bbot_server .
```

CI runs tests across Python 3.10-3.13 with `--reruns 2` for flaky test resilience.

## Engineering Principles

**No shortcuts. No hardcoding. No hacks.**

- **Build systems, not one-offs.** If you're building one of something and there will eventually be more, first build the proper generic system for it, then implement the specific instance within that system.
- **Modules own their data and code.** Any module-specific data or logic lives ONLY in that module's directory. No matching on module names. No branching on module types. The core system has zero knowledge of individual modules.
- **Generic over specific.** Always implement generic systems that work through interfaces and conventions, not through awareness of what's plugged into them. Modules register themselves; the core discovers and loads them uniformly.
- **Eat our own dogfood.** We use our own interfaces and abstractions. If something is awkward to use internally, it will be awkward for users too. Fix the abstraction. It's okay if we have to take a step back from the current task.

# MONGO TO POSTRES REFACTOR

This refactor is in-progress. here's our immediate TODO:

- get assets aggregation working properly. The assets module is meant to aggregate data from each child module recursively into an "Asset": a host with findings, technologies, open ports, etc. currently list_assets() yields bare hosts. A generic mechanism needs to be built for use in several of the asset endpoints, which pulls in data from those disparate tables and joins them on host.
- port events and watchdog, and get them working. this is an essential step which will ensures the testing framework is up and running, so we can finish porting the rest of the modules.
- note that we're not actually migrating existing data, so we don't need to worry about that

Later TODO:
- finish porting all modules and get their tests passing
- Implement alembic for migrations
- Make sure all data is stored within a single database, but that we have a reliable mechanism for separating event store, user store, and asset store. asset store is particularly important because its tables are dynamic and we need to have a programatic way to delete them (not only clear them), without inadvertently affecting any similarly-named tables tables that may exist.
