# AGENTS.md

A persistent database and CLI (bbctl) for BBOT scan data. Tests need MongoDB and Redis.

## Toolchain

| Concern | This repository |
|---|---|
| Language | Python 3.10 through 3.14 |
| Package manager | uv |
| Lint and format | ruff, pinned in pyproject.toml |
| Tests | pytest with pytest-asyncio |

## Setup

```bash
uv sync --group dev
```

## Tests

```bash
uv run pytest -v
uv run pytest -v -k test_applet_targets
```

## Standards

Org-wide, in [blacklanternsecurity/.github/standards](https://github.com/blacklanternsecurity/.github/tree/main/standards). Read the one your task touches, not all of them.

| Document | Read it when |
|---|---|
| [principles.md](https://github.com/blacklanternsecurity/.github/blob/main/standards/principles.md) | Always |
| [toolchain.md](https://github.com/blacklanternsecurity/.github/blob/main/standards/toolchain.md) | Touching dependencies, linting, formatting, or language versions |
| [git.md](https://github.com/blacklanternsecurity/.github/blob/main/standards/git.md) | Branching, commit messages, opening or reviewing a pull request |
| [rfc.md](https://github.com/blacklanternsecurity/.github/blob/main/standards/rfc.md) | A change needs agreement before work starts, or an RFC is ending |
| [testing.md](https://github.com/blacklanternsecurity/.github/blob/main/standards/testing.md) | Writing or changing tests, or anything that has them |
| [ci.md](https://github.com/blacklanternsecurity/.github/blob/main/standards/ci.md) | Touching a workflow, an action pin, or a permissions block |
| [releases.md](https://github.com/blacklanternsecurity/.github/blob/main/standards/releases.md) | Versioning, tagging, or publishing |
| [repository-setup.md](https://github.com/blacklanternsecurity/.github/blob/main/standards/repository-setup.md) | Creating a repository, or auditing one |

Never restate a standard here. If this file and a standard disagree, the standard wins and this file is the bug.

## Repository specifics

### Test services

Tests require MongoDB and Redis. Start them if they aren't already running:

```bash
# Start MongoDB (if not already running)
docker ps | grep -q mongo || docker run -d --name bbot-mongo --ulimit nofile=64000:64000 --rm -p 127.0.0.1:27017:27017 mongo

# Start Redis (if not already running)
docker ps | grep -q redis || docker run -d --name bbot-redis --rm -p 127.0.0.1:6379:6379 redis
```


### Test Framework

- Tests use **pytest** with **pytest-asyncio** (`asyncio_mode = "auto"`).
- Tests live in `tests/`.
- Test database config is in `tests/test_config.yml` (MongoDB: `mongodb://localhost:27017/test_bbot`, Redis: `redis://localhost:6379/15`).
- Database cleanup fixtures (`mongo_cleanup`, `redis_cleanup`) run before/after each test.

### Test Patterns

Features typically need **both** an API test and a CLI test:
- **API test** in `tests/test_applets/` : verifies the feature works through the Python and HTTP interfaces.
- **CLI test** in `tests/test_cli/` : verifies the feature is accessible and correct via `bbctl` command-line flags.

#### API Tests

- **Unit/integration tests** are async functions (`async def test_*`) that use the `bbot_server` fixture.
  - The `bbot_server` fixture is parametrized across `python` and `http` interfaces. Call it as `bbot_server = await bbot_server()`.
- **Applet lifecycle tests** inherit from `tests.test_applets.base.BaseAppletTest` and override `setup()`, `after_scan_1()`, `after_scan_2()`, `after_archive()`. Set `needs_worker = True` if the test requires a worker.
- Target models can be tested directly: `from bbot_server.modules.targets.targets_models import CreateTarget, Target`.

#### CLI Tests

- Use subprocess calls via `BBCTL_COMMAND` and the `bbot_server_http` fixture (see existing tests in `tests/test_cli/` for the pattern).
- Parse JSON output with `orjson.loads(process.stdout)`, check return codes and stderr messages.
