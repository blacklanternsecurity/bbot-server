from bbot.models.pydantic import Event
from bbot_server.applets._base import BaseApplet, api_endpoint
from bbot_server.asset_store.asset import Asset, AssetActivity


class Open_Ports(BaseApplet):
    watched_events = ["OPEN_TCP_PORT"]
    description = "open ports discovered during scans"
    route_prefix = ""

    async def ingest_event(self, asset: Asset, event: Event) -> list[AssetActivity]:
        activities = []
        if event.port:
            open_ports = self._get_open_ports(asset)
            if event.port not in open_ports:
                description = f"New open port: [{event.netloc}]"
                description_colored = f"New open port: [[dark_orange]{event.netloc}[/dark_orange]]"
                open_ports.add(event.port)
                open_ports = sorted(open_ports)
                open_port_activity = AssetActivity.create(
                    type="PORT_OPENED",
                    asset=asset,
                    event=event,
                    fieldname="open_ports",
                    value=open_ports,
                    description=description,
                    description_colored=description_colored,
                )
                activities.append(open_port_activity)
        return activities

    def _get_open_ports(self, asset: Asset) -> set[int]:
        return set(asset.fields.get("open_ports", [])) or set()

    @api_endpoint("/{host}/open_ports", methods=["GET"], summary="Get all the open ports for a host")
    async def get_open_ports(self, host: str) -> list[int]:
        print("GETTING OPEN PORTS", host)
