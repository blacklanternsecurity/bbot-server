from bbot.models.pydantic import Event
from bbot.core.helpers.misc import make_netloc
from bbot_server.models.assets import AssetActivity, BaseAssetFields
from bbot_server.applets._base import BaseApplet, api_endpoint, Annotated


from pydantic import BeforeValidator


def open_port_validator(value):
    return [] if not value else sorted(set(value))


class OpenPorts(BaseAssetFields):
    open_ports: Annotated[list[int], "indexed", BeforeValidator(open_port_validator)] = []  # noqa: F821

    def ingest_event(self, event: Event):
        self.open_ports = sorted(set(self.open_ports) | {event.port})

    def update_asset(self, asset):
        if self.open_ports:
            asset.open_ports = sorted(set(self.open_ports))
        else:
            asset.open_ports = []

    def diff(self, old) -> tuple[set[int], set[int]]:
        old_open_ports = set(old.open_ports)
        new_open_ports = set(self.open_ports)
        opened_ports = new_open_ports - old_open_ports
        closed_ports = old_open_ports - new_open_ports
        return opened_ports, closed_ports


class OpenPortsApplet(BaseApplet):
    name = "Open Ports"
    watched_events = ["OPEN_TCP_PORT"]
    description = "open ports discovered during scans"
    route_prefix = ""
    asset_fields = OpenPorts

    async def handle_event(self, event, asset):
        activities = []
        # get our fields from the asset
        old_obj = self.asset_fields.model_validate(asset, from_attributes=True)
        new_obj = self.asset_fields.model_validate(asset, from_attributes=True)
        # update the asset with the event data
        new_obj.ingest_event(event)
        new_obj.update_asset(asset)
        # diff the old and new asset
        opened_ports, _ = new_obj.diff(old_obj)
        for port in opened_ports:
            netloc = make_netloc(asset.host, port)
            activities.append(
                AssetActivity.from_event(
                    event,
                    type="PORT_OPENED",
                    description=f"New open port: [[dark_orange]{netloc}[/dark_orange]]",
                )
            )
        return activities

    @api_endpoint("/{host}/open_ports", methods=["GET"], summary="Get all the open ports for a host")
    async def get_open_ports(self, host: str) -> list[int]:
        asset = await self.collection.find_one({"host": str(host), "type": "Asset"}, {"open_ports": 1})
        if asset is None:
            return []
        return asset.get("open_ports", [])

    async def refresh(self, asset, events_by_type):
        """
        Refresh open ports for an asset (typically run after an archive)
        """
        ports = set()
        for event in events_by_type.get("OPEN_TCP_PORT", []):
            ports.add(event.port)

        old_open_ports = self.asset_fields.model_validate(asset, from_attributes=True)
        new_open_ports = self.asset_fields(open_ports=ports)
        opened_ports, closed_ports = new_open_ports.diff(old_open_ports)
        activities = []
        for port in opened_ports:
            netloc = make_netloc(asset.host, port)
            activities.append(
                AssetActivity(
                    host=asset.host,
                    netloc=netloc,
                    type="PORT_OPENED",
                    description=f"New open port: [[dark_orange]{netloc}[/dark_orange]]",
                )
            )
        for port in closed_ports:
            netloc = make_netloc(asset.host, port)
            activities.append(
                AssetActivity(
                    host=asset.host,
                    netloc=netloc,
                    type="PORT_CLOSED",
                    description=f"Closed port: [[dark_orange]{netloc}[/dark_orange]]",
                )
            )
        if activities:
            new_open_ports.update_asset(asset)
        return activities
