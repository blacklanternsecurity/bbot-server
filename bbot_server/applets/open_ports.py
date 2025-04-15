from bbot.core.helpers.misc import make_netloc
from bbot_server.assets.custom_fields import CustomAssetFields
from bbot_server.applets._base import BaseApplet, api_endpoint, Annotated


# add one field: 'open_ports' to the main asset model
class OpenPortsFields(CustomAssetFields):
    open_ports: Annotated[list[int], "indexed"] = []  # noqa: F821


class OpenPortsApplet(BaseApplet):
    name = "Open Ports"
    watched_events = ["OPEN_TCP_PORT"]
    description = "open ports discovered during scans"
    route_prefix = ""

    async def handle_event(self, event, asset):
        activities = []
        # get our fields from the asset
        old_open_ports = set(getattr(asset, "open_ports", []))
        if event.port not in old_open_ports:
            asset.open_ports = sorted(old_open_ports | {event.port})
            netloc = make_netloc(asset.host, event.port)
            activity = self.make_activity(
                type="PORT_OPENED",
                description=f"New open port: [[COLOR]{netloc}[/COLOR]]",
                detail={"port": event.port},
                event=event,
            )
            activities.append(activity)
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

        old_open_ports = set(asset.open_ports)
        new_open_ports = set(ports)
        opened_ports = new_open_ports - old_open_ports
        closed_ports = old_open_ports - new_open_ports
        asset.open_ports = sorted(new_open_ports)

        activities = []
        for port in opened_ports:
            netloc = make_netloc(asset.host, port)
            activities.append(
                self.make_activity(
                    host=asset.host,
                    netloc=netloc,
                    type="PORT_OPENED",
                    detail={"port": port},
                    description=f"New open port: [[COLOR]{netloc}[/COLOR]]",
                )
            )
        for port in closed_ports:
            netloc = make_netloc(asset.host, port)
            activities.append(
                self.make_activity(
                    host=asset.host,
                    netloc=netloc,
                    type="PORT_CLOSED",
                    detail={"port": port},
                    description=f"Closed port: [[COLOR]{netloc}[/COLOR]]",
                )
            )
        return activities
