# Plan: Port Events & Activity Modules to PostgreSQL

## Context

We're migrating bbot-server from MongoDB to PostgreSQL (`MONGO_POSTGRES_MIGRATION.md`). Phase 1 (foundation + shelving) and Phase 2 (targets, assets, findings, scans APIs) are complete. The base test harness (`tests/test_applets/base.py`) calls `insert_event()`, `tail_events()`, `tail_activities()`, and `archive_old_events()` — all from the shelved events and activity modules. Without these, most integration tests can't run. This change ports the events and activity modules to restore the test harness.

## Architecture Overview

### Event/Activity Flow
1. `insert_event(event)` publishes to Redis message queue
2. Watchdog (`bbot_server/watchdog/worker.py`) subscribes to queue, calls each loaded applet's `handle_event()`
3. `EventsApplet.handle_event()` writes event to DB
4. Other applets (findings, scans, etc.) generate `Activity` objects from events
5. Activities are published back to message queue
6. Watchdog subscribes to activity queue, calls each applet's `handle_activity()`
7. `ActivityApplet.handle_activity()` writes activity to DB

### Module Loading
`bbot_server/modules/__init__.py` auto-discovers files ending in `_api.py`. Shelved modules have been renamed to `.bak`, so they are **not loaded** — the watchdog simply doesn't call them.

## Key Design Decision: Models ARE the Tables, Defined Locally

Each module's model class is also its SQLModel table — no separate "Table" classes, no inheritance from external packages.

- **Event**: Redefine in `events_models.py` as our own `SQLModel, table=True` class with the same fields as bbot's `Event`. No import from `bbot.models.pydantic`. This gives us full control.
- **Activity**: Already ours. Make it directly a `SQLModel, table=True` class.

This keeps things DRY, avoids external dependencies for DB models, and keeps module-specific logic in the module.

## Steps

### 1. `bbot_server/modules/events/events_models.py` — Rewrite Event + fix EventsQuery

**Current state**: Has `EventsQuery(ActiveArchivedQuery)` with MongoDB dict-style `build()`, and `EventModel(Event)` inheriting from bbot's `Event`.

**Changes needed**:

**Replace `EventModel`** with a new `Event` class defined locally as `SQLModel, table=True`. No import from `bbot.models.pydantic`. Fields (same as bbot's Event):
```python
class Event(SQLModel, table=True):
    __tablename__ = "events"
    pk: int | None = Field(default=None, primary_key=True)
    uuid: str = Field(index=True, sa_column_kwargs={"unique": True})
    id: str = Field(index=True)
    type: str = Field(index=True)
    scope_description: str = ""
    data: str | None = Field(default=None, index=True)
    data_json: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    host: str | None = Field(default=None, index=True)
    port: int | None = None
    netloc: str | None = None
    resolved_hosts: list | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    dns_children: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    web_spider_distance: int = 10
    scope_distance: int = 10
    scan: str = Field(index=True)
    timestamp: float = Field(index=True)
    inserted_at: float | None = Field(default_factory=utc_now, index=True)
    parent: str = Field(default="", index=True)
    parent_uuid: str = Field(default="", index=True)
    tags: list | None = Field(default_factory=list, sa_column=Column(JSONB, server_default="[]"))
    module: str | None = Field(default=None, index=True)
    module_sequence: str | None = None
    discovery_context: str = ""
    discovery_path: list | None = Field(default_factory=list, sa_column=Column(JSONB, server_default="[]"))
    parent_chain: list | None = Field(default_factory=list, sa_column=Column(JSONB, server_default="[]"))
    archived: bool = Field(default=False, index=True)
    reverse_host: str | None = Field(default=None, index=True)
```

Keep `get_data()` method and `__hash__`. The `reverse_host` computed_field from bbot becomes a regular stored field — compute it on insert.

**EventsQuery.build()**: Replace MongoDB dict manipulation (lines 17-34) with SQLAlchemy `.where()`:
```python
async def build(self, applet=None):
    stmt = await super().build(applet)  # returns SQLAlchemy Select, not dict
    model = self._applet.model
    if self.min_timestamp is not None:
        stmt = stmt.where(model.timestamp >= self.min_timestamp)
    if self.max_timestamp is not None:
        stmt = stmt.where(model.timestamp <= self.max_timestamp)
    if self.scan is not None:
        stmt = stmt.where(model.scan == str(self.scan))
    if self.type is not None:
        stmt = stmt.where(model.type == self.type)
    return stmt
```

**Replace `build_search_query()`** (lines 36-53) with `_apply_search()`:
```python
async def _apply_search(self, stmt, model):
    search_str = self.search.strip().lower()
    if not search_str:
        return stmt
    from sqlalchemy import or_
    stmt = stmt.where(or_(
        model.type.ilike(f"{search_str.upper()}%"),
        model.host.ilike(f"{search_str}%"),
    ))
    return stmt
```

Parent chain: `EventsQuery` → `ActiveArchivedQuery` → `HostQuery` → `BaseQuery`. The parents already handle `archived`/`active`, `host`, `domain`, `search`, `sort`, `skip`/`limit`, and `query` (JSON filter) parameters.

### 2. `bbot_server/modules/activity/activity_models.py` — Make Activity a table + ActivityQuery.build()

**Current state**: Has `ActivityQuery(HostQuery)` with `type` field but no `build()` override, and `Activity(BaseHostModel)` with custom `__init__`, `set_event()`, `set_activity()`, computed `reverse_host`, cached `hash`.

**Changes needed**:

**Make `Activity` a SQLModel table**: Add `SQLModel, table=True` to `Activity`'s bases. Add `pk` primary key. Override `detail` field with JSONB column. Add `__tablename__ = "activities"`. The custom `__init__`, `set_event()`, `set_activity()`, computed fields all stay as-is.

**ActivityQuery.build()**: Add override:
```python
async def build(self, applet=None):
    stmt = await super().build(applet)
    model = self._applet.model
    if self.type is not None:
        stmt = stmt.where(model.type == self.type)
    return stmt
```

Parent chain: `ActivityQuery` → `HostQuery` → `BaseQuery`. Parents handle `host`, `domain`, `search`, `sort`, etc.

### 3. `bbot_server/db/postgres.py` — Register new tables

Add imports so SQLModel.metadata discovers the tables:
```python
import bbot_server.modules.events.events_models  # noqa: F401
import bbot_server.modules.activity.activity_models  # noqa: F401
```

### 4. `bbot_server/modules/events/events_api.py` — Create from `.bak`

**Reference**: `bbot_server/modules/events/events_api.py.bak`

Key changes from MongoDB to SQLAlchemy:
- `model = Event` (our new SQLModel Event from events_models)
- `handle_event(event, asset)`:
  - Was: `await self.collection.insert_one(event.model_dump())`
  - Now: `Event(**event.model_dump())` then `self._insert()`. Catch `IntegrityError` for duplicate uuids.
  - The `event` arg from the watchdog is bbot's pydantic Event; construct our Event from its dict.
- `get_event(uuid)`:
  - Was: `await self.collection.find_one({"uuid": uuid})`
  - Now: `await self._get_one(uuid=uuid)`
- `list_events(...)`:
  - Was: `query.mongo_iter(self)` yielding `Event(**event)`
  - Now: `query.query_iter(self)` — rows are our Event model directly
- `query_events(query)`:
  - Was: `query.mongo_iter(self)` yielding raw dicts
  - Now: `query.query_iter(self)`, call `row.model_dump()`
- `count_events(query)`:
  - Was: `query.mongo_count(self)` → Now: `query.query_count(self)`
- `tail_events(n)`: Unchanged — streams from message queue
- `archive_old_events(older_than)`: Same task management logic
- `_archive_events(older_than)`:
  - Was: `self.strict_collection.update_many(...)`
  - Now: SQLAlchemy `update(Event).where(Event.timestamp < archive_after, Event.archived != True).values(archived=True)`
  - Still calls `await self.root.assets.refresh_assets()` after archiving
- `consume_event_stream(generator)`: Unchanged — calls `self.insert_event(event)`

### 5. `bbot_server/modules/activity/activity_api.py` — Create from `.bak`

**Reference**: `bbot_server/modules/activity/activity_api.py.bak`

Key changes:
- `model = Activity` (now a SQLModel table)
- `handle_activity(activity, asset)`:
  - Was: `await self.collection.insert_one(activity.model_dump())`
  - Now: `Activity(**activity.model_dump())` then `self._insert()`
- `list_activities(host, type)`:
  - Was: `self.collection.find(query, sort=[...])`
  - Now: Build `ActivityQuery(host=host, type=type, sort=[("timestamp", 1), ("created", 1)])` and use `query.query_iter(self)`
- `query_activities(query)`:
  - Was: `query.mongo_iter(self)` → Now: `query.query_iter(self)`, yield `row.model_dump()`
- `count_activities(query)`:
  - Was: `query.mongo_count(self)` → Now: `query.query_count(self)`
- `tail_activities(n)`: Unchanged — streams from message queue

### 6. `bbot_server/models/base.py` — JSONB dot-notation in `_apply_json_filters()`

The events test at `tests/test_applets/test_applet_events.py:120` uses:
```python
query={"data_json.technology": {"$regex": "apache"}}
```

Current `_apply_json_filters()` does `getattr(model, "data_json.technology", None)` which returns `None`. Add dot-notation handling:

In the loop over `query_dict.items()`, before the `col = getattr(model, key, None)` check (around line 150), add:
```python
if "." in key:
    parts = key.split(".", 1)
    col = getattr(model, parts[0], None)
    if col is None:
        raise BBOTServerValueError(f"Unknown field: {parts[0]}")
    json_col = col[parts[1]].astext
    # Apply operators to the JSONB sub-field
    if isinstance(value, dict):
        for op, val in value.items():
            # reuse existing operator handling but on json_col
            ...
    else:
        conditions.append(json_col == str(value))
    continue
```

### 7. Update test skip markers

**Remove skip markers:**
- `tests/test_applets/test_applet_events.py` — remove `pytestmark` (line 4)
- `tests/test_applets/test_applet_scans.py` — remove `pytestmark` (line 4). Uses `insert_event` + `tail_activities` + scans API, all ported.
- `tests/test_message_queues.py` — remove `pytestmark` (line 3). Tests pub/sub + message flow, no shelved module deps.
- `tests/test_applets/test_applet_targets.py:test_applet_targets` — remove `@pytest.mark.skip` (line 10). Uses `tail_activities` which is now available.

**Keep skipped** (depend on shelved modules: dns_links, open_ports, technologies, cloud):
- `tests/test_applets/test_applet_activity.py` — asserts activity descriptions from shelved modules (e.g. "New DNS link", "New technology")
- `tests/test_applets/test_applet_assets.py` — checks Technology types, aggregation, cloud_providers
- `tests/test_applets/test_applet_findings.py` — checks `list_activities(type="NEW_FINDING")` + aggregation
- `tests/test_applets/test_applet_targets.py:TestTargetScopeMaintenance` — needs watchdog scope processing from shelved modules
- `tests/test_applets/test_applet_targets.py:TestTargetUpdateRemovesTargetFromAssets` — same

## Reference: Existing SQLAlchemy Patterns

### BaseApplet convenience methods (`bbot_server/applets/base.py`):
- `self.session()` — async session context manager
- `self._get_one(**filters)` — get single row
- `self._insert(obj)` — insert and refresh
- `self._update(filters, updates)` — update matching rows, returns rowcount
- `self._delete(**filters)` — delete matching rows
- `self._upsert(obj, conflict_columns)` — insert or update on conflict

### Query system (`bbot_server/models/base.py`):
- `BaseQuery.build(applet)` → returns SQLAlchemy `Select` statement
- `query.query_iter(applet)` → async iterate over rows
- `query.query_count(applet)` → count matching rows
- `_apply_json_filters(stmt, model, query_dict)` → translate MongoDB-style JSON filters to WHERE clauses

### Already-ported modules for reference:
- `bbot_server/modules/targets/targets_api.py` + `targets_models.py`
- `bbot_server/modules/assets/assets_api.py` + `assets_models.py`
- `bbot_server/modules/findings/findings_api.py` + `findings_models.py`
- `bbot_server/modules/scans/scans_api.py` + `scans_models.py`

### Existing centralized tables (`bbot_server/db/tables.py`):
Contains `AssetTable`, `FindingTable`, `TargetTable`, `ScanTable`. These should eventually be moved to their respective modules for consistency, but that's a separate cleanup.

## Verification
1. `uv run pytest tests/test_applets/test_applet_events.py -x -v --ignore=bbot-io-api-cluster`
2. `uv run pytest tests/test_applets/test_applet_targets.py -x -v --ignore=bbot-io-api-cluster`
3. `uv run pytest tests/ -x -v --ignore=bbot-io-api-cluster --exitfirst`

## Test flags
Always use `--exitfirst --ignore=bbot-io-api-cluster` when running tests.
