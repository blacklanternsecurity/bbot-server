# Plan: Remove Asset Model, Unify Table Models, Enable Watchdog with host_targets

## Context

The MongoDB→PostgreSQL migration removes the central "asset" model entirely. Previously, a monolithic Asset document stored summary data from all modules (findings, technologies, open_ports, etc.). Each module's `handle_event()` mutated this shared object, and the watchdog persisted it back.

With PostgreSQL, this is unnecessary. Each module has its own table. The "asset" concept is dead — there are only hosts, and each module stores its own data keyed by host. Target-scope mapping moves to a dedicated `host_targets` table. The watchdog simplifies: it just ensures the host is registered, then lets each applet write to its own table independently.

**Model unification principle**: One SQLModel `table=True` class per table, living in the module's `<module>_models.py`. No separate `*Table` classes in `db/tables.py`. This is what SQLModel was designed for. Computed fields handle display-only values (severity string, confidence string); stored columns handle everything that needs to be queried/filtered/indexed.

**Scope**: Architecture + findings as first facet. Target and Scan model unification noted but deferred.

---

## Step 0: `@derive` mechanism in base model

**File**: `bbot_server/models/base.py`

Add a `@derive` decorator and auto-computation in `BaseBBOTServerModel.__init__`. This eliminates repetitive `__init__` overrides for computing stored columns like `reverse_host`, `host_parts`, `netloc`, `id`, etc.

```python
def derive(field_name):
    """Mark a method as deriving a stored column value.

    The base __init__ calls all @derive methods after construction.
    Only sets the field if it's currently None (so DB-loaded rows aren't recomputed).
    """
    def decorator(fn):
        fn._derives = field_name
        return fn
    return decorator


class BaseBBOTServerModel(SQLModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # auto-compute derived stored fields
        for name in dir(self):
            method = getattr(type(self), name, None)
            field = getattr(method, '_derives', None)
            if field and getattr(self, field, None) is None:
                result = method(self)
                if result is not None:
                    setattr(self, field, result)

    def model_dump(self, *args, mode="json", exclude_none=True, **kwargs):
        return super().model_dump(*args, mode=mode, exclude_none=exclude_none, **kwargs)

    def sha1(self, data: str) -> str:
        return sha1(data.encode()).hexdigest()
```

Common derivations live in shared base classes and are inherited:

```python
class BaseHostModel(BaseBBOTServerModel):
    """Shared base for any model with a host column."""
    host: str = Field(index=True)
    reverse_host: str | None = Field(default=None, index=True)
    host_parts: list | None = Field(default=None, sa_column=Column(JSONB, nullable=True))

    @derive("reverse_host")
    def _derive_reverse_host(self):
        if self.host:
            return self.host[::-1]

    @derive("host_parts")
    def _derive_host_parts(self):
        if self.host:
            return re.split(r"[^a-z0-9]", self.host)
```

Module-specific derivations are added in the leaf model:

```python
class Finding(BaseHostModel, table=True):
    # ...
    @derive("id")
    def _derive_id(self):
        if self.description and self.netloc:
            return self.sha1(f"{self.description}:{self.netloc}")
```

---

## Step 1: Unify Finding model

### 1a. `bbot_server/modules/findings/findings_models.py`

Collapse `FindingTable` + `Finding` into a single `table=True` class inheriting from `BaseHostModel`.

Stored columns derived via `@derive`:
- `id` — SHA1 hash of `description:netloc`, primary lookup key
- `reverse_host` — reversed hostname for efficient domain filtering (inherited from BaseHostModel)
- `host_parts` — split hostname for search, JSONB (inherited from BaseHostModel)

Computed fields (display-only convenience, never stored or queried):
- `severity` — string version of `severity_score` (e.g. 4 → "HIGH")
- `confidence` — string version of `confidence_score` (e.g. 1 → "UNKNOWN")

Remove:
- `scope` field (moves to `host_targets` table)
- `type` field (implicit — each table knows what it is)

```python
class Finding(BaseHostModel, table=True):
    __tablename__ = "findings"

    pk: int | None = Field(default=None, primary_key=True)
    id: str = Field(index=True, sa_column_kwargs={"unique": True})
    port: int | None = Field(default=None)
    netloc: str | None = Field(default=None)
    url: str | None = Field(default=None)
    name: str = Field(index=True)
    description: str = ""
    verified: bool = Field(default=False, index=True)
    severity_score: int = Field(ge=1, le=5, index=True)
    confidence_score: int = Field(ge=1, le=5, default=1)
    temptation: int | None = Field(default=None)
    cves: list | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    created: float = Field(default_factory=utc_now, index=True)
    modified: float = Field(default_factory=utc_now, index=True)
    ignored: bool = False
    archived: bool = Field(default=False, index=True)

    def __init__(self, **kwargs):
        # convert severity/confidence strings to scores
        severity = kwargs.pop("severity", None)
        if severity is not None:
            kwargs["severity_score"] = SeverityScore.to_score(severity)
        confidence = kwargs.pop("confidence", None)
        if confidence is not None:
            kwargs["confidence_score"] = ConfidenceScore.to_score(confidence)
        # handle event
        event = kwargs.pop("event", None)
        super().__init__(**kwargs)
        if event is not None:
            self._set_event(event)

    def _set_event(self, event):
        """Copy host/port/url from a BBOT event."""
        if event.host and not self.host:
            self.host = event.host
        if event.port and not self.port:
            self.port = event.port
        if event.netloc and not self.netloc:
            self.netloc = event.netloc
        event_data_json = getattr(event, "data_json", None)
        if event_data_json is not None:
            url = event_data_json.get("url", None)
            if url is not None:
                self.url = url

    @derive("id")
    def _derive_id(self):
        if self.description and self.netloc:
            return self.sha1(f"{self.description}:{self.netloc}")

    @derive("netloc")
    def _derive_netloc(self):
        if self.host and self.port:
            return make_netloc(self.host, self.port)

    @computed_field
    @property
    def severity(self) -> str:
        return SeverityScore.to_str(self.severity_score)

    @computed_field
    @property
    def confidence(self) -> str:
        return ConfidenceScore.to_str(self.confidence_score)
```

Note: `reverse_host`, `host_parts` are inherited from `BaseHostModel` via `@derive` — no need to redeclare.

### 1b. `bbot_server/modules/findings/findings_api.py`

- Remove `from bbot_server.db.tables import FindingTable, AssetTable`
- Change `model = FindingTable` → `model = Finding`
- Delete `_to_pydantic()` and `_to_table()` — no more conversion needed
- Remove all `self._to_pydantic(row)` calls — query results are already Finding objects
- Update `handle_event()` and `_insert_or_update_finding()` (see Step 5c)

### 1c. Register Finding model in `db/postgres.py`

Add `import bbot_server.modules.findings.findings_models  # noqa: F401` so SQLModel.metadata sees the table.

---

## Step 2: New tables for hosts and host_targets

### 2a. `hosts` table

Lightweight host registry in `bbot_server/db/tables.py`. Only stores host identity — no module data.

```python
class Host(BaseHostModel, table=True):
    __tablename__ = "hosts"
    pk: int | None = Field(default=None, primary_key=True)
    created: float = Field(default_factory=utc_now, index=True)
    modified: float = Field(default_factory=utc_now, index=True)
    archived: bool = Field(default=False, index=True)
```

Inherits `host`, `reverse_host`, `host_parts` and their `@derive` methods from `BaseHostModel`.

### 2b. `host_targets` table

Normalized host→target mapping in `bbot_server/db/tables.py`. One row per (host, target_id) pair.

```python
class HostTarget(SQLModel, table=True):
    __tablename__ = "host_targets"
    pk: int | None = Field(default=None, primary_key=True)
    host: str = Field(index=True)
    target_id: str = Field(index=True)
    created: float = Field(default_factory=utc_now)
```

With a unique constraint on `(host, target_id)`.

### 2c. Delete `AssetTable` and `FindingTable` from `db/tables.py`

`FindingTable` is replaced by the unified `Finding` in `findings_models.py`. `AssetTable` is deleted entirely.

### 2d. Register new tables in `db/postgres.py`

---

## Step 3: Delete Asset model

### 3a. `bbot_server/assets.py`

Delete the file (or empty it). `Asset` and all related classes are gone.

### 3b. `bbot_server/models/base.py`

- Delete `BaseAssetFacet` class (had `scope`, `type`, `__store_type__`, `__table_name__`)
- `BaseHostModel` stays — now serves as shared base for Finding, Host, and future models
- `AssetQuery`: remove `_force_asset_type` pattern, update target_id filtering to use `host_targets` (see Step 6)

### 3c. Remove `Asset` imports everywhere

- `bbot_server/applets/base.py` — remove `from bbot_server.assets import Asset`
- `bbot_server/watchdog/worker.py` — remove `from bbot_server.assets import Asset`
- `bbot_server/modules/findings/findings_api.py` — remove `AssetTable` import
- `bbot_server/modules/targets/targets_api.py` — remove `AssetTable` import
- `bbot_server/modules/assets/assets_api.py` — complete rewrite (see Step 4)

---

## Step 4: Rewrite Assets applet

**File**: `bbot_server/modules/assets/assets_api.py`

The assets applet becomes a **query aggregation layer** over the `hosts` table + module tables.

- `model = Host` (from `db/tables.py`)
- Add `ensure_host_exists(host)` — upsert into hosts table, returns bool (is_new)
- `get_hosts()` — query Host table, optionally filtered by target via host_targets JOIN
- `get_asset(host)` — query Host row + enrich with findings from findings table
- `list_assets()` — stream Host rows (with optional findings enrichment)
- Remove: `update_asset()`, `_insert_asset()`, `_update_asset()`, `_get_asset()`, `refresh_assets()` (simplify later)

**File**: `bbot_server/modules/assets/assets_models.py`

- `AssetOnlyQuery` — remove `_force_asset_type`, queries Host table directly
- `AdvancedAssetQuery` — remove `type` field and routing (each module has its own table now)

---

## Step 5: Simplify watchdog + update handle_event/handle_activity signatures

### 5a. `bbot_server/watchdog/worker.py`

`_get_or_create_asset()` → `_ensure_host()`:

```python
async def _ensure_host(self, host, event=None, parent_activity=None):
    if not host:
        return None, []
    is_new = await self.bbot_server.assets.ensure_host_exists(host)
    activities = []
    if is_new:
        activities = [self.bbot_server.assets.make_activity(
            type="NEW_ASSET",
            description=f"New asset: [[COLOR]{host}[/COLOR]]",
            event=event, parent_activity=parent_activity,
        )]
    return host, activities
```

`_event_listener()` — pass `host` string, not Asset:

```python
async def _event_listener(self, message):
    event = Event(**message)
    host, activities = await self._ensure_host(event.host, event=event)
    for applet in self.bbot_server.all_child_applets(include_self=True):
        if not applet._enabled:
            continue
        if await applet.watches_event(event.type):
            _activities = await applet.handle_event(event, host) or []
            activities.extend(_activities)
    # NO update_asset() — each applet writes to its own table
    for activity in activities:
        await self.bbot_server._emit_activity(activity)
```

`_activity_listener()` — same pattern. Pass `host` string, remove `update_asset()` call.

### 5b. `BaseApplet` (`applets/base.py`)

Update signatures:
```python
async def handle_event(self, event, host=None):
    return []
async def handle_activity(self, activity, host=None):
    pass
```

Remove `from bbot_server.assets import Asset`.

### 5c. `FindingsApplet` (`findings/findings_api.py`)

`handle_event(self, event, host)`:
- Use `host` string directly: `Finding(host=host, ...)`
- Remove `finding.scope = asset.scope`
- Remove `asset.findings = sorted(...)` mutation
- Remove `asset.finding_severities` / `asset.finding_max_severity_score` mutations

`_insert_or_update_finding(finding, event)`:
- Remove `asset` parameter entirely
- Insert directly: `await self._insert(finding)` (Finding is now a table=True object)
- Remove all asset mutation code (lines 224-234)
- Remove `self.root._insert_asset(finding.model_dump())` → `await self._insert(finding)`

Delete `compute_stats()` entirely.

### 5d. `TargetsApplet` (`targets/targets_api.py`)

`handle_event(self, event, host)`:
- Read current scope from `host_targets` table instead of `asset.scope`
- Write scope changes to `host_targets` (INSERT/DELETE) instead of mutating `asset.scope`

`handle_activity(self, activity, host=None)`:
- Same — use host_targets for scope refresh

Add helper methods: `_add_host_target()`, `_remove_host_target()`, `_get_host_target_ids(host)`

`delete_target()`: simple `DELETE FROM host_targets WHERE target_id = :id` instead of JSONB array manipulation

### 5e. `EventsApplet`, `ScansApplet`, `ActivityApplet`

Change signatures to `handle_event(self, event, host)` / `handle_activity(self, activity, host)`. These don't use asset/host — just update the parameter name.

---

## Step 6: Update query classes

**File**: `bbot_server/models/base.py`

### 6a. `AssetQuery.build()` — target_id filtering via host_targets

Replace:
```python
stmt = stmt.where(model.scope.any(target_id))
```
With:
```python
from bbot_server.db.tables import HostTarget
stmt = stmt.where(model.host.in_(
    select(HostTarget.host).where(HostTarget.target_id == str(target_id))
))
```

### 6b. Remove `_force_asset_type` pattern

With separate tables, `type` filtering is implicit. Remove `_force_asset_type` from `AssetQuery` and `FindingsQuery`.

### 6c. Remove `scope` from query models

The `scope` field and `AssetQuery.scope` filtering are replaced by the host_targets subquery.

---

## Step 7: Update tests

### 7a. `test_applet_findings.py` — remove skip, adjust assertions
- Remove `pytestmark = pytest.mark.skip(...)`
- Line 55-56: `asset.findings == [...]` — this needs `get_asset()` to assemble findings from findings table. Keep if get_asset() supports it.
- Lines 144-148: Remove `query_findings(query=...)` with MongoDB `$regex` query (lines 144-148) — may need adjustment for Postgres regex
- Lines 150-157: Remove MongoDB aggregation assertions
- Lines 159-161: Remove MongoDB `count_findings(query=...)` — replace with Postgres-compatible
- Keep all other assertions (target filtering, domain filtering, severity filtering, search, count)

### 7b. `test_applet_assets.py` — remove skip, adjust assertions
- Remove `pytestmark = pytest.mark.skip(...)`
- Remove Technology assertions — module shelved
- Remove cloud_providers assertions — module shelved
- Remove MongoDB aggregation assertions
- Remove `$where`/`$out` sanitization tests — MongoDB-specific
- Keep host list assertions, pagination, search, target filtering, count, domain filtering

### 7c. `test_applet_targets.py` — unskip scope tests
- Remove skip markers for `TestTargetScopeMaintenance` and `TestTargetUpdateRemovesTargetFromAssets`
- These tests exercise target_id filtering which now goes through host_targets

### 7d. `test_archival.py` — leave skipped for now (depends on refresh_assets rework)

---

## Step 8: Verify

Run:
```bash
uv run pytest tests/test_applets/test_applet_events.py tests/test_applets/test_applet_findings.py tests/test_applets/test_applet_assets.py tests/test_applets/test_applet_targets.py tests/test_applets/test_applet_scans.py tests/test_message_queues.py -v
```

---

## Future work (not in this PR)

- **Unify Target model**: Collapse `TargetTable` + `Target` in `targets_models.py`. Computed fields (hash, target_hash, etc.) become stored columns via `@derive`.
- **Unify Scan model**: Collapse `ScanTable` + `Scan` in `scans_models.py`. Handle nested Target/Preset → JSONB serialization.
- **Port other modules**: Technologies, open_ports, cloud, DNS links — each gets its own unified table=True model.
- **Archival rework**: `refresh_assets()` adapts to new table structure.

---

## Critical files to modify

| File | Change |
|------|--------|
| `bbot_server/models/base.py` | Add `@derive` mechanism, remove BaseAssetFacet, remove scope/type from queries, host_targets subquery |
| `bbot_server/modules/findings/findings_models.py` | Unified `Finding` table=True class (replaces both Finding + FindingTable) |
| `bbot_server/modules/findings/findings_api.py` | Remove conversion methods, model=Finding, simplify handle_event |
| `bbot_server/db/tables.py` | Add Host, HostTarget; delete AssetTable, FindingTable |
| `bbot_server/db/postgres.py` | Register findings_models import |
| `bbot_server/assets.py` | Delete (remove Asset, BaseAssetFacet) |
| `bbot_server/watchdog/worker.py` | _ensure_host(), pass host string, remove update_asset() |
| `bbot_server/applets/base.py` | Update handle_event/handle_activity signatures, remove Asset import |
| `bbot_server/modules/assets/assets_api.py` | Rewrite: model=Host, ensure_host_exists(), virtual get_asset() |
| `bbot_server/modules/assets/assets_models.py` | Remove _force_asset_type, remove type routing |
| `bbot_server/modules/targets/targets_api.py` | host_targets CRUD, remove scope array manipulation |
| `bbot_server/modules/events/events_api.py` | Update handle_event signature |
| `bbot_server/modules/activity/activity_api.py` | Update handle_activity signature |
| `bbot_server/modules/scans/scans_api.py` | Update handle_event signature |
| `tests/test_applets/test_applet_findings.py` | Unskip, remove aggregation assertions |
| `tests/test_applets/test_applet_assets.py` | Unskip, remove technology/cloud/aggregation assertions |
| `tests/test_applets/test_applet_targets.py` | Unskip scope tests |
