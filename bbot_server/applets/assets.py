from sqlmodel import select
from typing import Optional, List

from bbot_server.models import AssetModel, AssetOutput, Event
from bbot_server.applets._base import BaseApplet, api_endpoint


class Assets(BaseApplet):

    description = "hostnames and IP addresses discovered during scans"
    data_model = AssetModel

    @api_endpoint("/{host}", methods=["GET"], summary="Get a single asset by its host")
    async def get_asset(self, host: str) -> AssetOutput:
        statement = select(self.model).where(self.model.host == host)
        asset_model = await self.db.find_one(statement)

        if asset_model:
            # Convert AssetModel to AssetOutput
            asset_output = AssetOutput(**asset_model.model_dump())

            # get all the events associated with this asset
            events = await self.parent.get_events_by_host(host)
            for event in events:
                asset_output.absorb_event(event)

            return asset_output

        return None  # Or raise an appropriate exception if the asset is not found

    @api_endpoint("/", methods=["GET"], summary="Get assets")
    async def get_assets(self, type: Optional[str] = None) -> list[str]:
        statement = select(self.model.host)
        if type is not None:
            statement = statement.where(self.model.type == type)
        return await self.db.find_many(statement)

    @api_endpoint("/", methods=["POST"], summary="Update or create an asset from an event")
    async def update_asset(self, event: Event):
        event = event.validated
        if event.host and event.type in ("DNS_NAME", "DNS_NAME_UNRESOLVED", "IP_ADDRESS", "IP_RANGE"):
            event_type = event.type if event.type != "DNS_NAME_UNRESOLVED" else "DNS_NAME"
            statement = select(self.model).where(self.model.host == event.host)
            asset = await self.db.find_one(statement)
            if not asset:
                asset = self.data_model(host=event.host, type=event_type, first_seen=event.timestamp)
            asset.last_seen = event.timestamp
            await self.db.insert_or_update(asset)

    # @api_endpoint("/summary", methods=["GET"], summary="Get summary of assets")
    # async def get_asset_summary(self) -> dict:
    #     statement = (
    #         select(self.model.host, self.model.type, func.count(self.model.id).label("count"))
    #         .where(self.model.host.is_not(None))
    #         .group_by(self.model.host, self.model.type)
    #     )
    #     results = await self.db.find_many(statement)
    #     result_dict = {}
    #     for host, _type, count in results:
    #         try:
    #             result_dict[host][_type] = count
    #         except KeyError:
    #             result_dict[host] = {_type: count}
    #     return result_dict

    # Implement these methods to fetch the additional data
    async def get_open_ports(self, host: str) -> List[int]:
        # Query your database to get open ports for the host
        # Return a list of integers
        pass

    async def get_web_screenshots(self, host: str) -> List[str]:
        # Query your database to get web screenshot UUIDs for the host
        # Return a list of strings (UUIDs)
        pass

    async def get_technologies(self, host: str) -> List[str]:
        # Query your database to get detected technologies for the host
        # Return a list of strings
        pass

    async def calculate_temptation(self, host: str) -> Optional[float]:
        # Implement your logic to calculate the temptation score
        # Return a float or None if not applicable
        pass
