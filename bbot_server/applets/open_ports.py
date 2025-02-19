from bbot.models.pydantic import Event
from bbot.core.helpers.misc import make_netloc
from bbot_server.models.assets import AssetActivity, BaseAssetFacet
from bbot_server.applets._base import BaseApplet, api_endpoint, Field, Annotated


class OpenPorts(BaseAssetFacet):
    open_ports: Annotated[list[int], "indexed"] = Field(default_factory=list)  # noqa: F821

    def ingest_event(self, event: Event):
        self.open_ports = sorted(set(self.open_ports) | {event.port})

    def diff(self, old, event=None) -> list[AssetActivity]:
        """
        Diff open ports between two assets (typically two versions of the same asset)

        Raise activities if any ports have opened or closed
        """
        new_open_ports = set(self.open_ports)
        old_open_ports = set(old.open_ports)
        old_self = old.model_dump()
        new_self = self.model_dump()
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
                    before=old_self,
                    after=new_self,
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
                    before=old_self,
                    after=new_self,
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
        open_ports_obj = await self._get_obj(host)
        if open_ports_obj is None:
            return []
        return open_ports_obj.open_ports

    async def ingest_event(self, event):
        open_ports = await self.get_open_ports(event.host)
        current_facet = self.model(host=event.host, open_ports=open_ports)
        activities = current_facet._ingest_event(event)
        if activities:
            await self._put_obj(current_facet)
        return activities

    # TODO: actually call this
    async def refresh(self, host):
        """
        Refresh open ports by host (typically run after an archive)
        """
        ports = set()
        async for e in self.event_store.get_events(host=host, type="OPEN_TCP_PORT"):
            port = getattr(e, "port", None)
            if port is not None:
                ports.add(port)
        new_open_ports = self.model(host=host, open_ports=ports)
        old_open_ports = await self._get_obj(host)
        activities = new_open_ports.diff(old_open_ports)
        if activities:
            await self._put_obj(new_open_ports)
        return activities
