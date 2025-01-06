from bbot.models.pydantic import Event
from bbot_server.applets._base import BaseApplet, api_endpoint
from bbot_server.asset_store.asset import Asset, AssetActivity


class Events(BaseApplet):
    description = "events"

    @api_endpoint("/ingest", methods=["POST"], summary="ingest a BBOT event into the asset database")
    async def ingest_event(self, event: Event) -> list[AssetActivity]:
        """
        ingest a BBOT event into the asset database

        This creates a list of activities that occurred as a result of the event (e.g. PORT_OPENED, CRITICAL_VULN, etc.).

        The activities are raised to subscribers and also returned to the caller.
        """
        # publish event to the message queue
        await self.root.message_queue.event_publish(event.model_dump())

        activities = []

        # we use a lock to prevent race conditions on the same asset
        async with self._asset_lock.lock(event.host):
            asset = None
            if event.host:
                # first try to get the asset based on the event's host
                asset = await self.root.assets.collection.find_one({"host": event.host})
                if asset is not None:
                    asset = Asset(**asset)
                else:
                    # if it doesn't exist, create it
                    asset = Asset(host=event.host)
                    await self.root.assets.collection.insert_one(asset.model_dump())
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

    @api_endpoint("/", methods=["GET"], summary="Get all events")
    async def get_events(self) -> list[Event]:
        events = await self.event_store.get_events()
        return events

    @api_endpoint("/{uuid}", methods=["GET"], summary="Get an event by its UUID")
    async def get_event(self, uuid: str) -> dict:
        print("GETTING EVENT", uuid)
