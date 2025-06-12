from bbot_server.assets import Asset
from bbot_server.utils.misc import utc_now
from bbot_server.applets.base import BaseApplet, api_endpoint


class AssetsApplet(BaseApplet):
    name = "Assets"
    description = "hostnames and IP addresses discovered during scans"
    attach_to = "root_applet"

    model = Asset

    @api_endpoint("/list", methods=["GET"], type="http_stream", response_model=Asset, summary="Stream all assets")
    async def get_assets(self, domain: str = None, target_id: str = None):
        """
        Stream all assets.

        Args:
            domain: Filter assets by domain or subdomain
            target_id: Filter assets by target ID or name
        """
        async for asset in self._get_assets(domain=domain, target_id=target_id):
            yield self.model(**asset)

    @api_endpoint("/{host}/detail", methods=["GET"], summary="Get a single asset by its host")
    async def get_asset(self, host: str) -> Asset:
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
            async for event in self.event_store.get_events(host=host):
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

    @api_endpoint("/hosts", methods=["GET"], summary="List hosts")
    async def get_hosts(self, domain: str = None, target_id: str = None) -> list[str]:
        """
        List all hosts.

        Args:
            domain: Return all hosts matching this domain (including subdomains)
            target_id: Only return hosts belonging to this target (can be either name or ID)
        """
        hosts = []
        async for asset in self._get_assets(domain=domain, target_id=target_id, fields=["host"]):
            host = asset.get("host", None)
            if host is not None:
                hosts.append(host)
        return sorted(hosts)

    async def _get_assets(
        self,
        query: dict = None,
        search: str = None,
        host: str = None,
        domain: str = None,
        type: str = "Asset",
        target_id: str = None,
        archived: bool = False,
        ignored: bool = False,
        fields: list[str] = None,
        sort: list[tuple[str, int]] = None,
    ):
        """
        Multipurpose async generator for getting assets from the database.

        Args:
            query: Additional query parameters (mongo)
            search: Search using mongo's text index
            host: Filter assets by host (exact match only)
            domain: Filter assets by domain (subdomains allowed)
            type: Filter assets by type (Asset, Technology, Vulnerability, etc.)
            target_id: Filter assets by target ID
            archived: Filter archived assets
            ignored: Filter ignored assets
            fields: List of fields to return
            sort: Fields and direction to sort by, e.g. sort=[("last_seen", -1)]
        """
        query = dict(query or {})
        query["archived"] = archived
        query["ignored"] = ignored
        if type is not None:
            query["type"] = type
        if host is not None:
            query["host"] = host
        if domain is not None:
            reversed_host = domain[::-1]
            # Match exact domain or subdomains (with dot separator)
            query["reverse_host"] = {"$regex": f"^{reversed_host}(\\.|$)"}
        if target_id is not None:
            target_query_kwargs = {}
            if target_id != "DEFAULT":
                target_query_kwargs["id"] = target_id
            target = await self.root.targets._get_target(**target_query_kwargs, fields=["id"])
            query["scope"] = target["id"]
        if search is not None:
            query["$text"] = {"$search": search}
        async for asset in self._query_assets(query, fields, sort):
            yield asset

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

    async def _query_assets(self, query: dict, fields: list[str] = None, sort: list[tuple[str, int]] = None):
        """
        Lowest-level query function for getting assets from the database.

        Args:
            query: Additional query parameters (mongo)
            fields: List of fields to return
            sort: Fields and direction to sort by, e.g. sort=[("last_seen", -1)]
        """
        self.log.debug(f"Querying assets: query={query} / fields={fields}")
        fields = {f: 1 for f in fields} if fields else None
        cursor = self.collection.find(query, fields)
        if sort:
            cursor = cursor.sort(sort)
        async for asset in cursor:
            yield asset

    async def _update_asset(self, host: str, update: dict):
        return await self.strict_collection.update_many({"host": host}, {"$set": update})

    async def _insert_asset(self, asset: dict):
        # we exclude scope here to avoid accidentally clobbering it
        asset.pop("scope", None)
        await self.strict_collection.insert_one(asset)
