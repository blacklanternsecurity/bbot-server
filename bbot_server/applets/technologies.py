from bbot_server.applets._base import BaseApplet, api_endpoint, BaseModel, Field


class Technologies(BaseApplet):
    name = "Technologies"
    watched_events = ["TECHNOLOGY"]
    description = "technologies discovered during scans"
    route_prefix = ""

    class AssetFields(BaseModel):
        technologies: list[str] = Field(default_factory=list)

    # async def handle_event(self, asset: Asset, event: Event) -> list[Activity]:
    #     activities = []
    #     technology = event.data["technology"]
    #     current_technologies = self._get_technologies(asset)
    #     if technology not in current_technologies:
    #         description = f"New technology: [{technology}]"
    #         description_colored = f"New technology: [[COLOR]{technology}[/COLOR]]"
    #         current_technologies.add(technology)
    #         current_technologies = sorted(current_technologies)
    #         technology_activity = Activity.create(
    #             type="NEW_TECHNOLOGY",
    #             asset=asset,
    #             event=event,
    #             fieldname="technologies",
    #             value=current_technologies,
    #             description=description,
    #             description_colored=description_colored,
    #         )
    #         activities.append(technology_activity)
    #     return activities

    def _get_technologies(self, asset) -> set[str]:
        return set(asset.fields.get("technologies", [])) or set()

    @api_endpoint("/{host}/technologies", methods=["GET"], summary="Get all the technologies for a host")
    async def get_technologies(self, host: str) -> list[str]:
        print("GETTING TECHNOLOGIES", host)
