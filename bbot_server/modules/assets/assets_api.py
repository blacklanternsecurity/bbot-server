from typing import Annotated
from fastapi import Path, Query
from sqlalchemy import select

from bbot_server.assets import Asset
from bbot_server.db.tables import AssetTable
from bbot_server.modules.assets.assets_models import AssetOnlyQuery, AdvancedAssetQuery
from bbot_server.utils.misc import utc_now
from bbot_server.applets.base import BaseApplet, api_endpoint


class AssetsApplet(BaseApplet):
    name = "Assets"
    description = "hostnames and IP addresses discovered during scans"

    model = AssetTable

    def _to_pydantic(self, row):
        """Convert an AssetTable row to a Pydantic Asset."""
        if row is None:
            return None
        return Asset(**row.model_dump())

    def _to_table(self, asset):
        """Convert a Pydantic Asset (or dict) to an AssetTable row for DB storage."""
        if isinstance(asset, dict):
            d = asset
        else:
            d = asset.model_dump()
        return AssetTable(**{k: v for k, v in d.items() if k != "pk"})

    @api_endpoint("/list", methods=["GET"], type="http_stream", response_model=Asset, summary="Stream all assets")
    async def list_assets(
        self,
        domain: Annotated[str, Query(description="Filter assets by domain or subdomain")] = None,
        target_id: Annotated[str, Query(description="Filter assets by target ID or name")] = None,
        limit: Annotated[int, Query(description="Limit the number of assets returned")] = None,
    ):
        """
        A simple, easily-curlable endpoint for listing assets, with basic filters
        """
        query = AssetOnlyQuery(domain=domain, target_id=target_id, limit=limit)
        async for row in query.query_iter(self):
            yield self._to_pydantic(row)

    @api_endpoint("/query", methods=["POST"], type="http_stream", response_model=dict, summary="Query assets")
    async def query_assets(self, query: AdvancedAssetQuery | None = None):
        """
        Advanced querying of assets. Choose your own filters and fields.
        """
        async for row in query.query_iter(self):
            d = row.model_dump()
            if query.fields:
                d = {k: v for k, v in d.items() if k in query.fields}
                d["_id"] = None  # backward compat
            yield d

    @api_endpoint("/count", methods=["POST"], summary="Count assets")
    async def count_assets(self, query: AdvancedAssetQuery | None = None) -> int:
        """
        Same as query_assets, except only returns the count
        """
        return await query.query_count(self)

    @api_endpoint("/{host}/detail", methods=["GET"], summary="Get a single asset by its host")
    async def get_asset(self, host: Annotated[str, Path(description="The host of the asset to get")]) -> Asset:
        row = await self._get_one(host=host, type="Asset")
        if not row:
            raise self.BBOTServerNotFoundError(f"Asset {host} not found")
        return self._to_pydantic(row)

    @api_endpoint(
        "/{host}/history", methods=["GET"], summary="Get the history of a single asset by its host", mcp=True
    )
    async def get_asset_history(self, host: str) -> list[str]:
        # Activity module is shelved; return empty for now
        return []

    @api_endpoint("/hosts", methods=["GET"], summary="List hosts")
    async def get_hosts(self, domain: str = None, target_id: str = None) -> list[str]:
        """
        List all hosts.

        Args:
            domain: Return all hosts matching this domain (including subdomains)
            target_id: Only return hosts belonging to this target (can be either name or ID)
        """
        hosts = []
        query = AssetOnlyQuery(domain=domain, target_id=target_id, fields=["host"])
        async for row in query.query_iter(self):
            host = row.host
            if host is not None:
                hosts.append(host)
        return sorted(hosts)

    async def update_asset(self, asset: Asset):
        asset.modified = utc_now()
        d = asset.model_dump()
        host = d.get("host")
        async with self.session() as session:
            stmt = select(AssetTable).where(AssetTable.host == host, AssetTable.type == "Asset")
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                for k, v in d.items():
                    if k not in ("pk",) and v is not None:
                        setattr(existing, k, v)
                existing.modified = utc_now()
                session.add(existing)
            else:
                row = AssetTable(**{k: v for k, v in d.items() if k != "pk"})
                session.add(row)
            await session.commit()

    async def refresh_assets(self):
        """
        Allow each child applet to refresh assets based on the current state of the event store.

        Typically run after an archival.
        """
        for host in await self.get_hosts():
            # get all the events for this host, and group them by type
            events_by_type = {}
            async for event in self.root.list_events(host=host):
                try:
                    events_by_type[event.type].add(event)
                except KeyError:
                    events_by_type[event.type] = {event}

            # get the asset for this host
            asset = await self.get_asset(host)

            # let each child applet do their thing based on the old asset and the current events
            for child_applet in self.all_child_applets(include_self=True):
                activities = await child_applet.refresh(asset, events_by_type)
                for activity in activities:
                    await self.emit_activity(activity)

            # update the asset with any changes made by the child applets
            await self.update_asset(asset)

    async def _get_asset(
        self,
        query: dict = None,
        host: str = None,
        type: str = "Asset",
        fields: list[str] = None,
    ):
        """Get a single asset matching the given filters."""
        filters = dict(query or {})
        if type is not None and "type" not in filters:
            filters["type"] = type
        if host is not None:
            filters["host"] = host
        async with self.session() as session:
            stmt = select(AssetTable)
            for k, v in filters.items():
                col = getattr(AssetTable, k, None)
                if col is not None:
                    stmt = stmt.where(col == v)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
        if row is None:
            return None
        if fields is not None:
            d = row.model_dump()
            if fields:
                d = {k: v for k, v in d.items() if k in fields}
            return d
        return row.model_dump()

    async def _update_asset(self, host: str, update: dict):
        """Update all assets matching the host."""
        await self._update({"host": host}, update)

    async def _insert_asset(self, asset: dict):
        """Insert a new asset row."""
        # we exclude scope here to avoid accidentally clobbering it
        # however we preserve scope for technologies and findings since they should inherit scope
        asset_type = asset.get("type", "Asset")
        if asset_type == "Asset":
            asset.pop("scope", None)
        row = AssetTable(**{k: v for k, v in asset.items() if k != "pk"})
        await self._insert(row)
