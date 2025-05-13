from bbot_server.assets.custom_fields import CustomAssetFields
from bbot_server.applets._base import BaseApplet, api_endpoint, Annotated


# add one field: 'open_ports' to the main asset model
class OpenPortsFields(CustomAssetFields):
    open_ports: Annotated[list[int], "indexed"] = []  # noqa: F821


class OpenPortsApplet(BaseApplet):
    name = "Open Ports"
    watched_events = ["OPEN_TCP_PORT"]
    watched_activities = ["PORT_OPENED", "PORT_CLOSED"]
    description = "open ports discovered during scans"

    async def handle_event(self, event, asset):
        """
        When a new OPEN_TCP_PORT event comes in, we check if it's already open, and raise an activity if it's new.
        """
        activities = []
        # get our fields from the asset
        old_open_ports = set(getattr(asset, "open_ports", []))
        if event.port not in old_open_ports:
            asset.open_ports = sorted(old_open_ports | {event.port})
            netloc = self.bbot_helpers.make_netloc(asset.host, event.port)
            activity = self.make_activity(
                type="PORT_OPENED",
                description=f"New open port: [[COLOR]{netloc}[/COLOR]]",
                detail={"port": event.port},
                event=event,
            )
            activities.append(activity)
        return activities

    async def compute_stats(self, asset, statistics):
        open_ports = getattr(asset, "open_ports", [])
        open_ports_stats = statistics.get("open_ports", {})
        for port in open_ports:
            # we convert to a string here, since JSON doesn't technically support int keys
            port = str(port)
            try:
                open_ports_stats[port] += 1
            except KeyError:
                open_ports_stats[port] = 1
        open_ports_stats = dict(sorted(open_ports_stats.items(), key=lambda x: x[1], reverse=True))
        statistics["open_ports"] = open_ports_stats

    @api_endpoint("/list", methods=["GET"], summary="Get all the open ports for all hosts")
    async def get_open_ports(self, domain: str = None, target_id: str = None) -> dict[str, list[int]]:
        open_ports = {}
        async for asset in self.parent._get_assets(
            # search for all assets with open ports
            query={"open_ports": {"$exists": True, "$ne": []}},
            target_id=target_id,
            fields=["host", "open_ports"],
        ):
            open_ports[asset["host"]] = asset["open_ports"]
        return open_ports

    @api_endpoint("/list/{host}", methods=["GET"], summary="Get all the open ports for a host")
    async def get_open_ports_by_host(self, host: str) -> list[int]:
        asset = await self.collection.find_one({"host": str(host), "type": "Asset"}, {"open_ports": 1})
        if asset is None:
            return []
        return asset.get("open_ports", [])

    @api_endpoint("/search/{port}", methods=["POST"], summary="Search for assets with a given open port", mcp=True)
    async def search_by_open_port(self, port: int, target_id: str = None) -> list[str]:
        assets = [
            a async for a in self.parent._get_assets(query={"open_ports": port}, target_id=target_id, fields=["host"])
        ]
        return [a.get("host") for a in assets]

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
            netloc = self.bbot_helpers.make_netloc(asset.host, port)
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
            netloc = self.bbot_helpers.make_netloc(asset.host, port)
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
