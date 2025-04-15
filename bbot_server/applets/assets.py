# applets imports
from bbot_server.applets.risk import Risk
from bbot_server.applets.emails import EmailsApplet
from bbot_server.applets.export import ExportApplet
from bbot_server.applets.findings import FindingsApplet
from bbot_server.applets.dns_links import DNSLinksApplet
from bbot_server.applets.open_ports import OpenPortsApplet
from bbot_server.applets.web_screenshots import WebScreenshotsApplet

from bbot_server.assets import Asset
from bbot_server.utils.misc import utc_now
from bbot_server.applets._base import BaseApplet, api_endpoint


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
    ]

    model = Asset

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
