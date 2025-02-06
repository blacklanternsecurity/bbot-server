from bbot.models.pydantic import Event
from bbot.core.helpers.misc import make_netloc
from bbot_server.models.assets import AssetActivity, BaseAssetFacet
from bbot_server.applets._base import BaseApplet, api_endpoint, Field, Annotated

class OpenPorts(BaseAssetFacet):
    open_ports: Annotated[list[int], "indexed"] = Field(default_factory=list)

    def ingest_event(self, event: Event):
        self.open_ports = sorted(set(self.open_ports) | {event.port})

    def diff(self, old, event=None) -> list[AssetActivity]:
        new_open_ports = set(self.open_ports)
        old_open_ports = set(old.open_ports)
        old_dict = old.model_dump()
        new_dict = self.model_dump()
        opened_ports = new_open_ports - old_open_ports
        closed_ports = old_open_ports - new_open_ports
        activities = []
        for port in opened_ports:
            netloc = make_netloc(self.host, port)
            activities.append(
                AssetActivity.create(
                    type="PORT_OPENED",
                    host=self.host,
                    event=event,
                    before=old_dict,
                    after=new_dict,
                    description=f"New open port: [[dark_orange]{netloc}[/dark_orange]]",
                )
            )
        for port in closed_ports:
            netloc = make_netloc(self.host, port)
            activities.append(
                AssetActivity.create(
                    type="PORT_CLOSED",
                    host=self.host,
                    event=event,
                    before=old_dict,
                    after=new_dict,
                    description=f"Closed port: [[dark_orange]{netloc}[/dark_orange]]",
                )
            )
        return activities


class OpenPortsApplet(BaseApplet):
    name = "Open Ports"
    watched_events = ["OPEN_TCP_PORT"]
    description = "open ports discovered during scans"
    route_prefix = ""
    model = OpenPorts

    @api_endpoint("/{host}/open_ports", methods=["GET"], summary="Get all the open ports for a host")
    async def get_open_ports(self, host: str) -> list[int]:
        return await self.collection.find_one({"host": host, "type": self.model.__name__}, {"open_ports": 1}) or []

    async def ingest_event(self, event):
        open_ports = await self.get_open_ports(event.host)
        current_facet = self.model(host=event.host, open_ports=open_ports)
        activities = current_facet._ingest_event(event)
        if activities:
            await self.strict_collection.update_one(
                {"host": event.host, "type": self.model.__name__},
                {"$set": current_facet.model_dump()},
                upsert=True,
            )
        return activities
