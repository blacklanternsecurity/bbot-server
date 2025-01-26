from bbot.models.pydantic import Event
from bbot_server.models.assets import Asset, AssetActivity
from bbot_server.applets._base import BaseApplet, api_endpoint


class Assets(BaseApplet):
    description = "hostnames and IP addresses discovered during scans"
    include_apps = ["Findings", "Open_Ports", "DNS_Links", "Emails", "Web_Screenshots", "Export"]
    fieldnames = ["host"]

    _data_model = Asset

    async def process_new_event(self, event: Event) -> list[AssetActivity]:
        activities = []

        # we use a lock to prevent race conditions on the same asset
        async with self._asset_lock.lock(event.host):
            asset = None
            if event.host:
                # first try to get the asset based on the event's host
                asset = await self.collection.find_one({"host": event.host})
                if asset is not None:
                    asset = Asset(**asset)
                else:
                    # if it doesn't exist, create it
                    asset = Asset(host=event.host)
                    await self.collection.insert_one(asset.model_dump())
                    new_asset_description = f"New asset [{event.host}] discovered"
                    new_asset_description_colored = f"New asset [[dark_orange]{event.host}[/dark_orange]] discovered"
                    new_asset_activity = AssetActivity(
                        type="NEW_ASSET",
                        event=event,
                        description=new_asset_description,
                        description_colored=new_asset_description_colored,
                    )
                    activities.append(new_asset_activity)

            # let the other modules ingest the event
            new_activities = await self.root._ingest_event(asset, event)
            activities.extend(new_activities)

            # publish activities to the message queue
            for activity in activities:
                await self.emit_activity(activity)

            # write the updated asset to the database
            if asset is not None:
                await self.root.assets.strict_collection.update_one({"host": event.host}, {"$set": asset.model_dump()})

        return activities

    @api_endpoint("/", methods=["GET"], summary="Get assets")
    async def get_assets(self) -> list[Asset]:
        cursor = self.collection.find()
        assets = await cursor.to_list(length=None)
        assets = [Asset(**asset) for asset in assets]
        return assets

    @api_endpoint("/{host}/list", methods=["GET"], summary="List assets by host (including subdomains)")
    async def get_assets_by_host(self, host: str) -> list[Asset]:
        cursor = self.collection.find({"reverse_host": {"$regex": f"^{host[::-1]}."}})
        assets = await cursor.to_list(length=None)
        assets = [Asset(**asset) for asset in assets]
        return assets

    @api_endpoint("/{host}/detail", methods=["GET"], summary="Get a single asset by its host")
    async def get_asset(self, host: str) -> Asset:
        asset = await self.collection.find_one({"host": host})
        if not asset:
            self.raise404("Asset not found")
        return Asset(**asset)

    @api_endpoint("/fieldnames", methods=["GET"], summary="List all current asset fieldnames")
    async def get_asset_fieldnames(self) -> list[str]:
        fieldnames = self.all_fieldnames
        return fieldnames
