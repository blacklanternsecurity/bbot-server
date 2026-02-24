from typing import Annotated
from fastapi import Path, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from bbot_server.db.tables import Host
from bbot_server.modules.assets.assets_models import AssetOnlyQuery, AdvancedAssetQuery
from bbot_server.utils.misc import utc_now
from bbot_server.applets.base import BaseApplet, api_endpoint


class AssetsApplet(BaseApplet):
    name = "Assets"
    description = "hostnames and IP addresses discovered during scans"

    model = Host

    async def ensure_host_exists(self, host: str) -> bool:
        """Upsert into hosts table. Returns True if the host is new."""
        existing = await self._get_one(host=host)
        if existing:
            return False
        new_host = Host(host=host)
        try:
            await self._insert(new_host)
        except IntegrityError:
            return False
        return True

    @api_endpoint("/list", methods=["GET"], type="http_stream", response_model=Host, summary="Stream all assets")
    async def list_assets(
        self,
        domain: Annotated[str, Query(description="Filter assets by domain or subdomain")] = None,
        target_id: Annotated[str, Query(description="Filter assets by target ID or name")] = None,
        limit: Annotated[int, Query(description="Limit the number of assets returned")] = None,
    ):
        query = AssetOnlyQuery(domain=domain, target_id=target_id, limit=limit)
        async for row in query.query_iter(self):
            yield row

    @api_endpoint("/query", methods=["POST"], type="http_stream", response_model=dict, summary="Query assets")
    async def query_assets(self, query: AdvancedAssetQuery | None = None):
        """
        Advanced querying of assets. Choose your own filters and fields.
        """
        async for row in query.query_iter(self):
            d = row.model_dump()
            if query.fields:
                d = {k: v for k, v in d.items() if k in query.fields}
            yield d

    @api_endpoint("/count", methods=["POST"], summary="Count assets")
    async def count_assets(self, query: AdvancedAssetQuery | None = None) -> int:
        return await query.query_count(self)

    @api_endpoint("/{host}/detail", methods=["GET"], summary="Get a single asset by its host")
    async def get_asset(self, host: Annotated[str, Path(description="The host of the asset to get")]) -> Host:
        row = await self._get_one(host=host)
        if not row:
            raise self.BBOTServerNotFoundError(f"Asset {host} not found")
        return row

    @api_endpoint(
        "/{host}/history", methods=["GET"], summary="Get the history of a single asset by its host", mcp=True
    )
    async def get_asset_history(self, host: str) -> list[str]:
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

    async def refresh_assets(self):
        """
        Allow each child applet to refresh assets based on the current state of the event store.

        Typically run after an archival.
        """
        for host in await self.get_hosts():
            events_by_type = {}
            async for event in self.root.list_events(host=host):
                try:
                    events_by_type[event.type].add(event)
                except KeyError:
                    events_by_type[event.type] = {event}

            asset = await self.get_asset(host)

            for child_applet in self.all_child_applets(include_self=True):
                activities = await child_applet.refresh(asset, events_by_type)
                for activity in activities:
                    await self.emit_activity(activity)
