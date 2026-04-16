# AGENTS.md

## Testing

- **Every feature must have a test.**
- **Every bug must have a regression test.**
- Bug fix workflow: FIRST write a test that expects proper behavior, verify it fails, THEN make the fix, and verify the test passes.

### Running Tests

Tests require MongoDB and Redis. Start them if they aren't already running:

```bash
# Start MongoDB (if not already running)
docker ps | grep -q mongo || docker run -d --name bbot-mongo --ulimit nofile=64000:64000 --rm -p 127.0.0.1:27017:27017 mongo

# Start Redis (if not already running)
docker ps | grep -q redis || docker run -d --name bbot-redis --rm -p 127.0.0.1:6379:6379 redis
```

Then run the tests:

```bash
# run all tests
uv run pytest -v

# run specific tests
uv run pytest -v -k test_applet_targets

# stop on first failure
uv run pytest -x
```

### Test Framework

- Tests use **pytest** with **pytest-asyncio** (`asyncio_mode = "auto"`).
- Tests live in `tests/`.
- Test database config is in `tests/test_config.yml` (MongoDB: `mongodb://localhost:27017/test_bbot`, Redis: `redis://localhost:6379/15`).
- Database cleanup fixtures (`mongo_cleanup`, `redis_cleanup`) run before/after each test.

### Test Patterns

Features typically need **both** an API test and a CLI test:
- **API test** in `tests/test_applets/` — verifies the feature works through the Python and HTTP interfaces.
- **CLI test** in `tests/test_cli/` — verifies the feature is accessible and correct via `bbctl` command-line flags.

#### API Tests

- **Unit/integration tests** are async functions (`async def test_*`) that use the `bbot_server` fixture.
  - The `bbot_server` fixture is parametrized across `python` and `http` interfaces. Call it as `bbot_server = await bbot_server()`.
- **Applet lifecycle tests** inherit from `tests.test_applets.base.BaseAppletTest` and override `setup()`, `after_scan_1()`, `after_scan_2()`, `after_archive()`. Set `needs_worker = True` if the test requires a worker.
- Target models can be tested directly: `from bbot_server.modules.targets.targets_models import CreateTarget, Target`.

#### CLI Tests

- Use subprocess calls via `BBCTL_COMMAND` and the `bbot_server_http` fixture (see existing tests in `tests/test_cli/` for the pattern).
- Parse JSON output with `orjson.loads(process.stdout)`, check return codes and stderr messages.
