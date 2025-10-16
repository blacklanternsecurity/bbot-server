from typing import Annotated
from fastapi import Body, Path, Query

from bbot_server.assets import Asset
from bbot_server.utils.misc import utc_now
from bbot_server.applets.base import BaseApplet, api_endpoint


class AssetsApplet(BaseApplet):
    name = "Assets"
    description = "hostnames and IP addresses discovered during scans"

    model = Asset

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
        async for asset in self.mongo_iter(type="Asset", domain=domain, target_id=target_id, limit=limit):
            yield self.model(**asset)

    @api_endpoint("/query", methods=["POST"], type="http_stream", response_model=dict, summary="Query assets")
    async def query_assets(
        self,
        query: Annotated[dict, Body(description="Raw mongo query")] = None,
        search: Annotated[str, Body(description="Search using mongo's text index")] = None,
        host: Annotated[str, Body(description="Filter assets by host (exact match only)")] = None,
        domain: Annotated[str, Body(description="Filter assets by domain (subdomains allowed)")] = None,
        type: Annotated[
            str, Body(description="Filter assets by type (Asset, Technology, Vulnerability, etc.)")
        ] = "Asset",
        target_id: Annotated[str, Body(description="Filter assets by target ID")] = None,
        archived: Annotated[bool, Body(description="Whether to include archived assets")] = False,
        active: Annotated[bool, Body(description="Whether to include active assets")] = True,
        ignored: Annotated[bool, Body(description="Filter on whether the asset is ignored")] = False,
        fields: Annotated[list[str], Body(description="List of fields to return")] = None,
        limit: Annotated[int, Body(description="Limit the number of assets returned")] = None,
        sort: Annotated[list[str | tuple[str, int]], Body(description="Fields and direction to sort by")] = None,
        aggregate: Annotated[list[dict], Body(description="Optional custom MongoDB aggregation pipeline")] = None,
    ) -> list[Asset]:
        """
        Advanced querying of assets. Choose your own filters and fields.
        """
        async for asset in self.mongo_iter(
            query=query,
            search=search,
            host=host,
            domain=domain,
            type=type,
            target_id=target_id,
            archived=archived,
            active=active,
            ignored=ignored,
            fields=fields,
            limit=limit,
            sort=sort,
            aggregate=aggregate,
        ):
            yield asset

    @api_endpoint("/{host}/detail", methods=["GET"], summary="Get a single asset by its host")
    async def get_asset(self, host: Annotated[str, Path(description="The host of the asset to get")]) -> Asset:
        asset = await self.collection.find_one({"host": host})
        if not asset:
            raise self.BBOTServerNotFoundError(f"Asset {host} not found")
        return self.model(**asset)

    @api_endpoint(
        "/{host}/history", methods=["GET"], summary="Get the history of a single asset by its host", mcp=True
    )
    async def get_asset_history(self, host: str) -> list[str]:
        query = {}
        if host:
            query["host"] = host
        history = []
        async for activity in self.root.activity.collection.find(
            query, {"description": 1}, sort=[("timestamp", 1), ("created", 1)]
        ):
            history.append(activity["description"])
        return history

    @api_endpoint("/hosts", methods=["GET"], summary="List hosts")
    async def get_hosts(self, domain: str = None, target_id: str = None) -> list[str]:
        """
        List all hosts.

        Args:
            domain: Return all hosts matching this domain (including subdomains)
            target_id: Only return hosts belonging to this target (can be either name or ID)
        """
        hosts = []
        async for asset in self.mongo_iter(type="Asset", domain=domain, target_id=target_id, fields=["host"]):
            host = asset.get("host", None)
            if host is not None:
                hosts.append(host)
        return sorted(hosts)

    async def update_asset(self, asset: Asset):
        asset.modified = utc_now()
        await self.strict_collection.update_one({"host": asset.host}, {"$set": asset.model_dump()}, upsert=True)

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
                    await self._emit_activity(activity)

            # update the asset with any changes made by the child applets
            await self.update_asset(asset)

    async def make_bbot_query(self, type: str = "Asset", query: dict = None, ignored: bool = False, **kwargs):
        """
        Extension of make_bbot_query for assets and asset facets (findings, technologies, etc.)
        """
        query = dict(query or {})
        # "ignored" field is unique to assets and asset facets
        if ignored is not None and "ignored" not in query:
            query["ignored"] = ignored
        return await super().make_bbot_query(type=type, query=query, **kwargs)

    async def _get_asset(
        self,
        query: dict = None,
        host: str = None,
        type: str = "Asset",
        fields: list[str] = None,
    ):
        query = dict(query or {})
        if type is not None and "type" not in query:
            query["type"] = type
        if host is not None:
            query["host"] = host
        return await self.collection.find_one(query, fields)

    async def _update_asset(self, host: str, update: dict):
        return await self.strict_collection.update_many({"host": host}, {"$set": update})

    async def _insert_asset(self, asset: dict):
        # we exclude scope here to avoid accidentally clobbering it
        # however we preserve scope for technologies and findings since they should inherit scope
        asset_type = asset.get("type", "Asset")
        if asset_type == "Asset":
            asset.pop("scope", None)
        await self.strict_collection.insert_one(asset)
