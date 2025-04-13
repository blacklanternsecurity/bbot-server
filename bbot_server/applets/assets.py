import inspect
from contextlib import suppress

# applets imports
from bbot_server.applets.risk import Risk
from bbot_server.applets.emails import EmailsApplet
from bbot_server.applets.export import ExportApplet
from bbot_server.applets.findings import FindingsApplet
from bbot_server.applets.dns_links import DNSLinksApplet
from bbot_server.applets.open_ports import OpenPortsApplet
from bbot_server.applets.scans.targets import TargetsApplet
from bbot_server.applets.web_screenshots import WebScreenshotsApplet

from bbot_server.applets._base import BaseApplet, api_endpoint
from bbot_server.models.assets import Activity, BaseAssetFacet
from bbot_server.utils.misc import combine_pydantic_models, utc_now


class Asset(BaseAssetFacet):
    __tablename__ = "assets"


class AssetsApplet(BaseApplet):
    name = "Assets"
    description = "hostnames and IP addresses discovered during scans"
    include_apps = [
        FindingsApplet,
        OpenPortsApplet,
        DNSLinksApplet,
        EmailsApplet,
        WebScreenshotsApplet,
        ExportApplet,
        Risk,
        TargetsApplet,
    ]

    model = Asset

    async def setup(self):
        self.log.critical("SETUP ASSETS")
        global Asset
        asset_field_models = set()
        for child_applet in self.all_child_applets():
            asset_field_model = getattr(child_applet, "asset_fields", None)
            if asset_field_model is not None:
                await self.build_indexes(asset_field_model)
                asset_field_models.add(asset_field_model)
        master_asset_model = combine_pydantic_models(asset_field_models, model_name="Asset", base_model=BaseAssetFacet)

        self.model = master_asset_model
        Asset = master_asset_model

        # everything from here down is ugly and unfortunate but necessary
        # because we're modifying the Asset model at runtime, and we need to update
        # the type annotations for FastAPI to pick up on the changes
        # TODO: find a better way to do this

        # Update the response_model in the api_endpoint decorators
        for method_name, method in inspect.getmembers(self.__class__, predicate=inspect.isfunction):
            # Update response_model in api_endpoint decorators
            kwargs = getattr(method, "_kwargs", {})
            response_model = kwargs.get("response_model", None)
            if response_model is not None:
                if response_model.__name__ == "Asset":
                    kwargs["response_model"] = master_asset_model
                    setattr(method, "_kwargs", kwargs)

            # Update type annotations in method signatures
            signature = inspect.signature(method)
            return_annotation = signature.return_annotation
            if hasattr(return_annotation, "__name__") and return_annotation.__name__ == "Asset":
                method.__annotations__["return"] = master_asset_model
            elif isinstance(return_annotation, list) or getattr(return_annotation, "__origin__", None) is list:
                args = getattr(return_annotation, "__args__", None)
                if args and len(args) == 1 and hasattr(args[0], "__name__") and args[0].__name__ == "Asset":
                    method.__annotations__["return"] = list[master_asset_model]

    @api_endpoint("/", methods=["GET"], type="http_stream", response_model=Asset, summary="Stream all assets")
    async def get_assets(self):
        async for asset in self.collection.find({"type": "Asset"}):
            yield self.model(**asset)

    @api_endpoint("/{host}/list", methods=["GET"], summary="List assets by host (including subdomains)")
    async def get_assets_by_host(self, host: str) -> list[Asset]:
        cursor = self.collection.find({"type": "asset", "reverse_host": {"$regex": f"^{host[::-1]}."}})
        assets = await cursor.to_list(length=None)
        assets = [self.model(**asset) for asset in assets]
        return assets

    @api_endpoint("/{host}/detail", methods=["GET"], summary="Get a single asset by its host")
    async def get_asset(self, host: str) -> Asset:
        asset = await self.collection.find_one({"host": host})
        if not asset:
            raise self.BBOTServerNotFoundError(f"Asset {host} not found")
        return self.model(**asset)

    @api_endpoint("/tail", type="websocket_stream_outgoing", response_model=Activity)
    async def tail_assets(self, n: int = 0):
        agen = self.message_queue.asset_tail(n=n)
        try:
            async for activity in agen:
                yield activity
        finally:
            with suppress(BaseException):
                await agen.aclose()

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

    @api_endpoint("/hosts", methods=["GET"], summary="List all hosts")
    async def get_hosts(self) -> list[str]:
        cursor = self.collection.find({"archived": False, "ignored": False})
        hosts = await cursor.distinct("host")
        hosts.sort()
        return hosts
