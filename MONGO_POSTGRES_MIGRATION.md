# MongoDB to PostgreSQL Migration Plan

## Context

bbot-server currently uses three MongoDB databases (asset store, user store, event store) with pymongo, a custom annotation-based index system, and a `CustomAssetFields` mechanism that merges module fields into a monolithic Asset model at import time via AST parsing. We are migrating to a single PostgreSQL database using SQLModel (single class = Pydantic + SQLAlchemy table), eliminating `CustomAssetFields` by giving each module its own table, and exposing a clean Python API for direct SQLAlchemy queries. This is a clean-slate migration (no data migration script).

---

## 1. New Model Layer: SQLModel

Each model is a single SQLModel class that serves as both the Pydantic API model and the SQLAlchemy table definition. Complex Postgres features (JSONB, TSVECTOR, generated columns) use `sa_column()`.

### Base classes

**File: `bbot_server/db/base.py`** (replace current contents)

```python
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, String, Float, Boolean, Text, Integer, func, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID, JSONB, TSVECTOR
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import Computed

class BBOTServerModel(SQLModel):
    """Abstract base for all bbot-server models."""
    class Config:
        arbitrary_types_allowed = True

class BaseHostModel(BBOTServerModel):
    """Base for models with host/port/netloc."""
    host: str = Field(index=True)
    port: int | None = Field(default=None, index=True)
    netloc: str | None = Field(default=None, index=True)
    url: str | None = Field(default=None, index=True)
    reverse_host: str | None = Field(
        default=None,
        sa_column=Column(String, Computed("reverse(host)"), nullable=True)
    )
    created: float = Field(default_factory=utc_now, index=True)
    modified: float = Field(default_factory=utc_now, index=True)
    ignored: bool = False
    archived: bool = Field(default=False, index=True)
    # tsvector for full-text search - overridden per model with specific fields
    search_vector: str | None = Field(
        default=None,
        sa_column=Column(TSVECTOR, nullable=True)
    )
```

### Example module model: Finding

```python
class Finding(BaseHostModel, table=True):
    __tablename__ = "findings"
    pk: int | None = Field(default=None, primary_key=True)
    id: str = Field(index=True, unique=True)  # computed in Python: sha1(description:netloc)
    scope: list = Field(default_factory=list, sa_column=Column(ARRAY(UUID), default=[]))
    name: str = Field(index=True)
    description: str
    verified: bool = Field(default=False, index=True)
    severity_score: int = Field(ge=1, le=5, index=True)
    confidence_score: int = Field(ge=1, le=5, default=1)
    temptation: int | None = Field(default=None, ge=1, le=5)
    cves: list | None = Field(default=None, sa_column=Column(JSONB, nullable=True))

    @property
    def severity(self) -> str:
        return SeverityScore.to_str(self.severity_score)

    @property
    def confidence(self) -> str:
        return ConfidenceScore.to_str(self.confidence_score)
```

Search vectors populated via PostgreSQL trigger (created in Alembic migration) rather than `Computed()`, since tsvector expressions referencing multiple columns work better as triggers.

---

## 2. Database Schema: All Tables

Single PostgreSQL database: `bbot_server`

| Table | Replaces | Key columns |
|-------|----------|-------------|
| `assets` | `bbot_assetstore.assets` (type=Asset only) | pk, host, port, netloc, url, reverse_host, created, modified, ignored, archived, scope (UUID[]) |
| `findings` | `bbot_assetstore.assets` (type=Finding) | pk, id (unique), host, netloc, scope, name, description, severity_score, confidence_score, verified, temptation, cves (JSONB) |
| `technologies` | `bbot_assetstore.assets` (type=Technology) | pk, id (unique), host, netloc, scope, technology, last_seen |
| `open_ports` | Asset.open_ports field | pk, host, port, scope, created, UNIQUE(host, port) |
| `dns_links` | Asset.dns_links field | pk, host, rdtype, target_host, scope, UNIQUE(host, rdtype, target_host) |
| `cloud_providers` | Asset.cloud_providers field | pk, host, provider, scope, UNIQUE(host, provider) |
| `activities` | `bbot_assetstore.history` | pk, id (UUID unique), host, netloc, type, timestamp, created, archived, description, description_colored, detail (JSONB), module, scan, parent_event_uuid, parent_event_id |
| `events` | `bbot_eventstore.events` | pk, uuid (unique), id, type, host, netloc, data, data_json (JSONB), scan, timestamp, inserted_at, parent, parent_uuid, tags (JSONB), module, archived, dns_children (JSONB), resolved_hosts (JSONB) |
| `targets` | `bbot_userstore.targets` | pk, id (UUID unique), name (unique), description, target (JSONB), seeds (JSONB), blacklist (JSONB), strict_dns_scope, hash, created, modified |
| `scans` | `bbot_userstore.scans` | pk, id (unique), name (unique), description, status_code, status, agent_id, target (JSONB snapshot), preset (JSONB snapshot), created, started_at, finished_at, duration_seconds |
| `presets` | `bbot_userstore.presets` | pk, id (UUID unique), name, preset (JSONB), created, modified |
| `agents` | `bbot_userstore.agents` | pk, id (UUID unique), name (unique), description, connected, status, current_scan_id, last_seen |

Key design decisions:
- **Scan embeds Target/Preset as JSONB snapshots** (not FK references) since they represent point-in-time state
- **`scope` is `UUID[]`** with GIN index for target-based filtering
- **`reverse_host`** is a generated column: `reverse(host)` for subdomain queries
- **Full-text search** via `search_vector` (TSVECTOR) column + GIN index, populated by triggers

---

## 3. What Gets Eliminated

### Removed systems
- **`CustomAssetFields`** - entire AST-parsing merge system in `modules/__init__.py`
- **`combine_pydantic_models()`** in `utils/misc.py`
- **`_sanitize_mongo_query()` / `_sanitize_mongo_aggregation()`** in `utils/misc.py`
- **`utils/db.py`** - MongoDB index utilities (desired_indexes_from_model, compute_index_diff, etc.)
- **`store.py`** - BaseMongoStore, AssetStore, UserStore, EventStore
- **`reconcile_all_indexes()`** in `applets/base.py` - replaced by Alembic
- **Aggregation pipeline support** - dropped from query API
- **Summary fields on Asset** - `findings`, `finding_severities`, `finding_max_severity`, `finding_max_severity_score`, `technologies`, `open_ports`, `dns_links`, `cloud_providers` all removed from the Asset model (each module has its own table now)
- **`compute_stats()`** pattern on applets - replaced with efficient SQL GROUP BY queries

### Removed from each module's `*_api.py`
- All `CustomAssetFields` subclasses (OpenPortsFields, FindingFields, TechnologiesFields, DNSLinks, CloudFields)
- All code that mutates Asset fields (e.g., `asset.findings = sorted(findings)`)

---

## 4. New Query System

Replace MongoDB query dicts with SQLAlchemy statement builders. Keep the same class hierarchy.

**File: `bbot_server/models/base.py`** (rewrite query classes)

```python
class BaseQuery(BaseModel):
    query: dict | None = None    # Simplified JSON filter (translated to SQL WHERE)
    search: str | None = None    # Full-text search via tsvector
    fields: list[str] | None = None
    skip: int | None = None
    limit: int | None = None
    sort: list[str | tuple[str, int]] | None = None
    # aggregate: DROPPED

    def build(self, applet) -> Select:
        model = applet.model
        stmt = select(model)
        if self.query:
            stmt = _apply_json_filters(stmt, model, self.query)
        if self.search:
            ts_query = func.plainto_tsquery("simple", self.search.strip())
            stmt = stmt.where(model.search_vector.op("@@")(ts_query))
        if self.sort:
            for field, direction in self.sort:
                col = getattr(model, field)
                stmt = stmt.order_by(desc(col) if direction == -1 else asc(col))
        if self.skip:
            stmt = stmt.offset(self.skip)
        if self.limit:
            stmt = stmt.limit(self.limit)
        return stmt
```

### JSON filter translation (`_apply_json_filters`)

Supports a subset of MongoDB-style operators, translated to SQLAlchemy:

| JSON operator | SQL equivalent |
|---------------|---------------|
| `{"field": value}` | `field = value` |
| `{"field": {"$gt": v}}` | `field > v` |
| `{"field": {"$gte": v}}` | `field >= v` |
| `{"field": {"$lt": v}}` | `field < v` |
| `{"field": {"$lte": v}}` | `field <= v` |
| `{"field": {"$ne": v}}` | `field != v` |
| `{"field": {"$in": [...]}}` | `field IN (...)` |
| `{"field": {"$nin": [...]}}` | `field NOT IN (...)` |
| `{"field": {"$regex": "..."}}` | `field ~ '...'` (Postgres regex) |
| `{"field": {"$exists": true}}` | `field IS NOT NULL` |
| `{"$and": [...]}` | `AND(...)` |
| `{"$or": [...]}` | `OR(...)` |
| `{"$text": {"$search": "..."}}` | `search_vector @@ plainto_tsquery(...)` |

Unknown operators raise `BBOTServerValueError`. This keeps API compatibility while simplifying.

### Query execution on applets

```python
# BaseApplet gains:
async def query_iter(self, query):
    """Async iterate over query results, yielding model instances."""
    stmt = await query.build(self)
    async with self.session() as session:
        result = await session.execute(stmt)
        for row in result.scalars():
            yield row

async def query_count(self, query):
    stmt = await query.build(self)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    async with self.session() as session:
        result = await session.execute(count_stmt)
        return result.scalar()
```

---

## 5. BaseApplet Changes

**File: `bbot_server/applets/base.py`**

Replace MongoDB collection references with SQLAlchemy session factory:

```python
class BaseApplet:
    model = None          # SQLModel class (is both Pydantic + table)
    _session_factory = None  # async_sessionmaker, inherited from root

    async def _native_setup(self):
        if self.parent is not None:
            self._session_factory = self.parent._session_factory
            self.message_queue = self.parent.message_queue
            self.task_broker = self.parent.task_broker
            if self.model is None:
                self.model = self.parent.model
        # ...

    def session(self):
        """Get an async session context manager."""
        return self._session_factory()

    # Convenience methods replacing MongoDB operations:
    async def _get_one(self, **filters):
        async with self.session() as session:
            stmt = select(self.model)
            for k, v in filters.items():
                stmt = stmt.where(getattr(self.model, k) == v)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def _insert(self, obj):
        async with self.session() as session:
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return obj

    async def _upsert(self, obj, conflict_columns: list[str]):
        from sqlalchemy.dialects.postgresql import insert
        async with self.session() as session:
            values = {c.key: getattr(obj, c.key) for c in self.model.__table__.columns if getattr(obj, c.key, None) is not None}
            stmt = insert(self.model).values(**values)
            update_cols = {k: v for k, v in values.items() if k not in conflict_columns}
            stmt = stmt.on_conflict_do_update(index_elements=conflict_columns, set_=update_cols)
            await session.execute(stmt)
            await session.commit()

    async def _update(self, filters: dict, updates: dict):
        from sqlalchemy import update
        async with self.session() as session:
            stmt = update(self.model)
            for k, v in filters.items():
                stmt = stmt.where(getattr(self.model, k) == v)
            stmt = stmt.values(**updates)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

    async def _delete(self, **filters):
        from sqlalchemy import delete as sa_delete
        async with self.session() as session:
            stmt = sa_delete(self.model)
            for k, v in filters.items():
                stmt = stmt.where(getattr(self.model, k) == v)
            await session.execute(stmt)
            await session.commit()
```

Remove: `self.collection`, `self.strict_collection`, `self.asset_store`, `self.user_store`, `self.event_store`, `self.db`, `reconcile_all_indexes()`.

---

## 6. RootApplet Changes

**File: `bbot_server/applets/_root.py`**

```python
class RootApplet(BaseApplet):
    async def setup(self):
        if self.is_native:
            from bbot_server.db.postgres import create_db
            self.engine, self._session_factory = await create_db()

            from bbot_server.message_queue import MessageQueue
            self.message_queue = MessageQueue()
            await self.message_queue.setup()

        await self._setup()
        return True, ""

    async def cleanup(self):
        if self.is_native:
            await self.engine.dispose()
            await self.message_queue.cleanup()
        await self._cleanup()
```

---

## 7. New Database Store

**File: `bbot_server/db/postgres.py`** (new)

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import SQLModel
from bbot_server.config import BBOT_SERVER_CONFIG as bbcfg

async def create_db():
    engine = create_async_engine(bbcfg.database.uri, echo=False, pool_size=10, max_overflow=20)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    # Create tables (dev/test). In production, use Alembic.
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine, session_factory
```

---

## 8. Config Changes

**File: `bbot_server/config.py`**

```python
class DatabaseConfig(BaseModel):
    uri: str  # e.g. "postgresql+asyncpg://localhost:5432/bbot_server"

class BBOTServerSettings(BaseSettings):
    # ...
    database: DatabaseConfig  # NEW: single Postgres connection
    message_queue: MessageQueueConfig
    # REMOVE: event_store, asset_store, user_store
```

**File: `bbot_server/defaults.yml`**

```yaml
database:
  uri: postgresql+asyncpg://localhost:5432/bbot_server
message_queue:
  uri: redis://localhost:6379/0
```

**File: `pyproject.toml`**

Remove: `pymongo`
Add: `sqlmodel`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `greenlet`

---

## 9. Incremental Module Strategy

### Philosophy: Start small, get green, then expand

Instead of rewriting all ~14 modules at once, we **shelve** non-essential modules (rename `*_api.py` -> `*_api.py.bak`, comment out their tests) and focus on getting the core working end-to-end first. This means the server boots, connects to Postgres, and the core modules' tests pass before we touch anything else.

### 9a. Phase 1 Modules (migrate these first)

**Assets (`modules/assets/`)** — the core table, required by everything
- Slim down `Asset` model: remove all module-injected fields
- `assets_api.py`: Replace `collection.find_one()` with `_get_one()`, `collection.update_one()` with `_upsert()`, etc.
- Remove `_get_asset()` / `_update_asset()` / `_insert_asset()` MongoDB helpers, replace with SQLAlchemy equivalents
- For now, stats that joined multiple modules (findings count per asset, etc.) can return empty/zero — they'll be wired up when those modules come back online

**Findings (`modules/findings/`)** — a good second module to prove the pattern
- Delete `FindingFields(CustomAssetFields)` class
- `Finding` becomes a standalone SQLModel table
- `handle_event()`: Insert into `findings` table directly, stop mutating `asset.findings`, `asset.finding_severities`, etc.
- `finding_counts()` and `severity_counts()` become `SELECT name, COUNT(*) FROM findings GROUP BY name` style queries
- `_insert_or_update_finding()`: Use `_upsert()` on `id` column

**Targets (`modules/targets/`)** — needed for scans, straightforward CRUD
- `Target` becomes its own SQLModel table
- Replace all MongoDB operations with SQLAlchemy equivalents

**Scans (`modules/scans/`)** — needed for end-to-end testing
- `Scan` becomes SQLModel table with `target` and `preset` as JSONB columns (snapshots, not FKs)
- Replace `collection.insert_one()` / `collection.update_one()` / `collection.find_one()` with SQLAlchemy

### 9b. Shelved Modules (rename to `.bak`, comment out tests)

These modules get their `*_api.py` renamed to `*_api.py.bak` so the module loader in `modules/__init__.py` skips them. Their corresponding tests get commented out or skipped. They remain in the codebase untouched and can be brought back one at a time.

| Module | Files to shelve | Notes |
|--------|----------------|-------|
| `technologies/` | `technologies_api.py` -> `.bak` | Has `CustomAssetFields` — will need rewrite |
| `open_ports/` | `open_ports_api.py` -> `.bak` | Has `CustomAssetFields` — will need rewrite |
| `dns/dns_links/` | `dns_links_api.py` -> `.bak` | Has `CustomAssetFields` — will need rewrite |
| `cloud/` | `cloud_api.py` -> `.bak` | Has `CustomAssetFields` — will need rewrite |
| `events/` | `events_api.py` -> `.bak` | Simple insert pattern, easy to bring back |
| `activity/` | `activity_api.py` -> `.bak` | Simple insert pattern, easy to bring back |
| `emails/` | `emails_api.py` -> `.bak` | |
| `agents/` | `agents_api.py` -> `.bak` | |
| `presets/` | `presets_api.py` -> `.bak` | |
| `stats/` | `stats_api.py` -> `.bak` | Depends on other modules being online |

### 9c. Bringing Shelved Modules Back (phase 2+)

Once Assets + Findings + Targets + Scans are working and green, bring modules back one at a time:

1. **Rename** `*_api.py.bak` back to `*_api.py`
2. **Rewrite** MongoDB calls to use the new SQLAlchemy helpers (`_get_one`, `_insert`, `_upsert`, etc.)
3. **Delete** any `CustomAssetFields` subclass in that file
4. **Define** the module's SQLModel table (if it needs its own table)
5. **Uncomment** its tests, run them, fix until green
6. **Move on** to the next module

Suggested order for bringing modules back:
1. Events, Activity (high-value, simple insert/query pattern)
2. Technologies (has `CustomAssetFields`, but simple table)
3. Open Ports (standalone table with unique constraint)
4. DNS Links, Cloud (standalone tables)
5. Agents, Presets (straightforward CRUD)
6. Emails, Stats (depend on other modules)

---

## 10. Module Loading (`modules/__init__.py`)

**Major simplification.** Remove:
- `ASSET_FIELD_MODELS` list
- `check_for_asset_field_models()` function and all AST parsing
- `combine_pydantic_models()` call
- The preloading phase that scans for `CustomAssetFields` subclasses

The `Asset` class is now defined simply:

```python
class Asset(BaseHostModel, table=True):
    __tablename__ = "assets"
    pk: int | None = Field(default=None, primary_key=True)
    scope: list = Field(default_factory=list, sa_column=Column(ARRAY(UUID), default=[]))
    # That's it. No more module-injected fields.
```

Module loading continues to load `*_api.py` files for applet registration and `*_cli.py` for CLI modules, but the `CustomAssetFields` preloading pass is completely removed.

---

## 11. Python Developer API

```python
from bbot_server import BBOTServer
from sqlalchemy import select, func

server = BBOTServer()
await server.setup()

# High-level API (unchanged)
async for finding in server.list_findings(domain="evilcorp.com"):
    print(finding.name, finding.severity)

# Direct SQLAlchemy API (new)
model = server.open_ports.model  # the OpenPort SQLModel class
stmt = select(model).where(model.port == 443).order_by(model.host)
async with server.session() as session:
    result = await session.execute(stmt)
    for row in result.scalars():
        print(row.host, row.port)

# Aggregation replacement example
stmt = (
    select(server.findings.model.name, func.count())
    .group_by(server.findings.model.name)
    .order_by(func.count().desc())
)
async with server.session() as session:
    for name, count in (await session.execute(stmt)).all():
        print(f"{name}: {count}")
```

---

## 12. Full-Text Search Strategy

- Each table that needs text search gets a `search_vector TSVECTOR` column
- Populated by a PostgreSQL trigger (created in Alembic migration):
  ```sql
  CREATE FUNCTION findings_search_trigger() RETURNS trigger AS $$
  BEGIN
    NEW.search_vector := to_tsvector('simple', coalesce(NEW.name, '') || ' ' || coalesce(NEW.description, '') || ' ' || coalesce(NEW.host, ''));
    RETURN NEW;
  END $$ LANGUAGE plpgsql;
  ```
- GIN index on `search_vector` for fast lookups
- Queries use `plainto_tsquery('simple', search_term)` matching
- This replaces MongoDB's `$text` search with equivalent functionality
- The `'simple'` dictionary is used (like MongoDB) for language-agnostic tokenization

---

## 13. Subdomain Matching Strategy

Current approach: `reverse_host` field + `$regex: "^moc.proclivee"` for left-anchored index scan.

New approach (same concept, native Postgres):
- `reverse_host` as a `GENERATED ALWAYS AS (reverse(host)) STORED` column
- B-tree index on `reverse_host`
- Query: `WHERE reverse_host LIKE 'moc.proclivee.%' OR reverse_host = 'moc.proclivee'`
- B-tree indexes support `LIKE 'prefix%'` patterns efficiently

---

## 14. Docker Compose Changes

Replace MongoDB service with PostgreSQL:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: bbot_server
      POSTGRES_USER: bbot
      POSTGRES_PASSWORD: bbot
    ports:
      - "5432:5432"
    volumes:
      - ./pgdata:/var/lib/postgresql/data
```

---

## 15. Implementation Phases

### Phase 1: Foundation + Shelve

**Goal:** Server boots, connects to Postgres, zero modules loaded. Tests infrastructure works.

- Add dependencies to `pyproject.toml` (`sqlmodel`, `sqlalchemy[asyncio]`, `asyncpg`, `greenlet`; keep `pymongo` for now)
- Create `bbot_server/db/postgres.py` (engine, session factory, `SQLModel.metadata.create_all`)
- Update `config.py` with `DatabaseConfig`, update `defaults.yml`
- Update `compose.yml` — add Postgres service (keep MongoDB temporarily for reference)
- Shelve non-essential modules: rename `*_api.py` -> `*_api.py.bak` for: technologies, open_ports, dns/dns_links, cloud, events, activity, emails, agents, presets, stats
- Comment out / `pytest.mark.skip` tests for shelved modules
- Remove `CustomAssetFields` system from `modules/__init__.py` (delete AST parsing, `combine_pydantic_models()` call, `ASSET_FIELD_MODELS`)
- Delete `bbot_server/assets.py` `CustomAssetFields` base class (no module uses it anymore in phase 1)
- Rewrite `BaseApplet` to use `_session_factory` instead of `collection`/`db`/stores
- Add `_get_one()`, `_insert()`, `_upsert()`, `_update()`, `_delete()` convenience methods
- Rewrite `RootApplet.setup()` to call `create_db()` instead of setting up 3 MongoDB stores
- Update `tests/conftest.py`: replace `mongo_cleanup` with Postgres table truncation, update test config
- **Checkpoint:** server boots, connects to Postgres, no import errors

### Phase 2: Core Modules (Assets + Findings + Targets + Scans)

**Goal:** The 4 core modules work end-to-end, their tests pass.

- Define SQLModel tables: `Asset`, `Finding`, `Target`, `Scan`
- Rewrite `assets_api.py` — replace all MongoDB calls with SQLAlchemy helpers
- Rewrite `findings_api.py` — standalone `Finding` table, delete `FindingFields`, rewrite queries
- Rewrite `targets_api.py` — straightforward CRUD migration
- Rewrite `scans_api.py` — JSONB snapshots for target/preset
- Rewrite `BaseQuery.build()` to produce SQLAlchemy `Select` statements
- Implement `_apply_json_filters()` for MongoDB-style query compatibility
- Rewrite corresponding `*_models.py` files
- Update/write tests for these 4 modules
- **Checkpoint:** `pytest tests/test_assets.py tests/test_findings.py tests/test_targets.py tests/test_scans.py` all green

### Phase 3: Bring Back Remaining Modules (one at a time)

**Goal:** Each shelved module is un-shelved, rewritten, and tested individually.

Suggested order:
1. **Events + Activity** — high-value, simple insert/query pattern
2. **Technologies** — has `CustomAssetFields` to delete, simple standalone table
3. **Open Ports** — standalone table with `(host, port)` unique constraint
4. **DNS Links + Cloud** — standalone normalized tables
5. **Agents + Presets** — straightforward CRUD
6. **Emails + Stats** — may depend on other modules being online

For each module:
1. Rename `*_api.py.bak` -> `*_api.py`
2. Define its SQLModel table
3. Rewrite MongoDB calls to SQLAlchemy helpers
4. Delete any `CustomAssetFields` subclass
5. Uncomment its tests, run, fix until green

### Phase 4: Cleanup

**Goal:** Remove all MongoDB remnants, finalize.

- Delete `store.py`, `utils/db.py`
- Remove `_sanitize_mongo_query()`, `_sanitize_mongo_aggregation()`, `combine_pydantic_models()` from `utils/misc.py`
- Remove `pymongo` from `pyproject.toml`
- Remove MongoDB service from `compose.yml`
- Update watchdog worker
- Set up Alembic for production migrations (optional — `create_all` is fine for dev/test)
- Final full test suite run

---

## 16. Files Summary

### New files
- `bbot_server/db/postgres.py` - Engine + session factory
- `bbot_server/db/query.py` - JSON-to-SQL filter translation

### Shelved files (renamed to `.bak` in Phase 1, restored in Phase 3)
- `technologies/technologies_api.py`
- `open_ports/open_ports_api.py`
- `dns/dns_links/dns_links_api.py`
- `cloud/cloud_api.py`
- `events/events_api.py`
- `activity/activity_api.py`
- `emails/emails_api.py`
- `agents/agents_api.py`
- `presets/presets_api.py`
- `stats/stats_api.py`

### Deleted files (Phase 4)
- `bbot_server/store.py`
- `bbot_server/utils/db.py`

### Heavily modified files (Phase 1-2)
- `bbot_server/db/base.py` - Becomes SQLModel base classes
- `bbot_server/config.py` - DatabaseConfig replaces 3x StoreConfig
- `bbot_server/defaults.yml` - Single `database.uri`
- `bbot_server/applets/base.py` - Session-based instead of collection-based
- `bbot_server/applets/_root.py` - Postgres setup replaces 3x MongoDB stores
- `bbot_server/modules/__init__.py` - Remove CustomAssetFields merging
- `bbot_server/assets.py` - Remove CustomAssetFields class
- `bbot_server/models/base.py` - Rewrite query classes
- `tests/conftest.py` - Postgres fixtures replace mongo_cleanup
- `pyproject.toml` - Add sqlmodel/asyncpg deps
- `compose.yml` - Add Postgres service

### Phase 1-2 module files (rewritten)
- `modules/assets/assets_api.py`, `assets_models.py`
- `modules/findings/findings_api.py`, `findings_models.py`
- `modules/targets/targets_api.py`, `targets_models.py`
- `modules/scans/scans_api.py`, `scans_models.py`

### Phase 4 deletions
- `bbot_server/utils/misc.py` - Remove Mongo sanitizers (`_sanitize_mongo_query`, `_sanitize_mongo_aggregation`, `combine_pydantic_models`)
- `bbot_server/utils/db.py` - Remove entirely
- `bbot_server/store.py` - Remove entirely

### Verification (per-phase)
**After Phase 2:**
- `pytest tests/test_assets.py tests/test_findings.py tests/test_targets.py tests/test_scans.py` — all green
- Server boots and connects to Postgres without import errors
- Core API endpoints return correct data shapes

**After Phase 3 (each module):**
- Module's own tests pass after un-shelving
- No regressions in previously-passing tests

**After Phase 4:**
- Full `pytest` suite green
- No pymongo imports remain
- `grep -r pymongo bbot_server/` returns nothing
- Docker compose boots cleanly with only Postgres + Redis
