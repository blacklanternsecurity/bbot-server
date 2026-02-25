# Plan: Dynamic asset enrichment via child applets

## Context

`list_assets()` currently yields bare `Host(pk, host)` objects. An "asset" should include data from all child applets (findings, technologies, etc.). The enrichment should be dynamic — any child applet of AssetsApplet with its own model/table should automatically contribute to the asset view, with no hard-coding in the assets module.

We'll use GROUP BY + array_agg for now. If it becomes a bottleneck at scale, we can switch to LATERAL JOIN later.

## Approach

### 1. Each child applet declares how it contributes to the asset view

In `bbot_server/applets/base.py`, add to BaseApplet:

- `asset_field: str = ""` — the key name in the asset dict (e.g. `"findings"`, `"technologies"`). Empty means "don't participate." One applet, one field.
- `def asset_summary(self)` — returns a SQLAlchemy expression describing the per-host summary for this applet (e.g. an aggregated list of finding names). Returns `None` by default (don't participate).
- `def asset_join(self, host_column)` — returns a SQLAlchemy join condition. Default: `self.model.host == host_column`.

### 2. Build the enriched query dynamically in AssetsApplet

In `bbot_server/modules/assets/assets_api.py`, rewrite `list_assets()`:

```python
stmt = select(Host.host)

for applet in self.child_applets:
    summary = applet.asset_summary()
    if summary is not None:
        stmt = stmt.outerjoin(applet.model, applet.asset_join(Host.host))
        stmt = stmt.add_columns(summary)

stmt = stmt.group_by(Host.host)
```

The assets applet doesn't know or care what's inside the expressions. It just asks each child for a join condition and a summary.

### 3. FindingsApplet implements asset_summary()

In `bbot_server/modules/findings/findings_api.py`:

```python
asset_field = "findings"

def asset_summary(self):
    from sqlalchemy import func, distinct
    return (
        func.array_agg(distinct(self.model.name))
            .filter(self.model.name.isnot(None))
            .label(self.asset_field)
    )
```

Future applets (technologies, open_ports) each define their own summary. A technology applet might aggregate differently than findings.

### 4. End result

After scan 1, `list_assets()` yields dicts like:

```json
{"host": "www.evilcorp.com", "findings": ["CVE-2024-12345"]}
{"host": "evilcorp.com", "findings": []}
{"host": "1.2.3.4", "findings": []}
```

If TechnologiesApplet existed, it would automatically add another LEFT JOIN and the output would include `"technologies"` too — no changes to AssetsApplet needed.

### 5. Update the test

In `tests/test_applets/test_applet_assets.py`, update `after_scan_1()`:

- `list_assets()` now yields dicts instead of Host objects
- Each dict has `"host"` + one key per child applet (e.g. `"findings"`)
- After scan 1, `www.evilcorp.com` and `www2.evilcorp.com` have `"findings": ["CVE-2024-12345"]`
- Other hosts have `"findings": []`

## Files to modify

1. `bbot_server/applets/base.py` — add `asset_field`, `asset_summary()`, `asset_join()` defaults
2. `bbot_server/modules/assets/assets_api.py` — rewrite `list_assets()` to build dynamic JOIN query
3. `bbot_server/modules/findings/findings_api.py` — set `asset_field`, implement `asset_summary()`
4. `tests/test_applets/test_applet_assets.py` — update `after_scan_1()` assertions

## Verification

Run `pytest tests/test_applets/test_applet_assets.py::TestAppletAssets -x -v` and verify `after_scan_1()` passes.
