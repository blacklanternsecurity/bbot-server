from bbot.models.pydantic import Event
from bbot_server.models.assets import Asset, AssetActivity
from bbot_server.applets._base import BaseApplet, api_endpoint


class Technologies(BaseApplet):
    watched_events = ["TECHNOLOGY"]
    description = "technologies discovered during scans"
    route_prefix = ""
    fieldnames = ["technologies"]

    async def ingest_event(self, asset: Asset, event: Event) -> list[AssetActivity]:
        activities = []
        technology = event.data["technology"]
        current_technologies = self._get_technologies(asset)
        if technology not in current_technologies:
            description = f"New technology: [{technology}]"
            description_colored = f"New technology: [[dark_orange]{technology}[/dark_orange]]"
            current_technologies.add(technology)
            current_technologies = sorted(current_technologies)
            technology_activity = AssetActivity.create(
                type="NEW_TECHNOLOGY",
                asset=asset,
                event=event,
                fieldname="technologies",
                value=current_technologies,
                description=description,
                description_colored=description_colored,
            )
            activities.append(technology_activity)
        return activities

    def _get_technologies(self, asset: Asset) -> set[str]:
        return set(asset.fields.get("technologies", [])) or set()

    @api_endpoint("/{host}/technologies", methods=["GET"], summary="Get all the technologies for a host")
    async def get_technologies(self, host: str) -> list[str]:
        print("GETTING TECHNOLOGIES", host)
