from typing import Any
from bbot_server.models.technology_models import Technology
from bbot_server.assets.custom_fields import CustomAssetFields
from bbot_server.applets._base import BaseApplet, api_endpoint, Annotated


# add one field: 'technologies' to the main asset model
class TechnologiesFields(CustomAssetFields):
    technologies: Annotated[list[str], "indexed", "indexed-text"] = []  # noqa: F821


class TechnologiesApplet(BaseApplet):
    name = "Technologies"
    watched_events = ["TECHNOLOGY"]
    description = "technologies discovered during scans"
    model = Technology

    @api_endpoint("/get/{id}", methods=["GET"], summary="Get a technology by ID")
    async def get_technology(self, id: str) -> Technology:
        return Technology(**(await self.root._get_asset(type="Technology", id=id)))

    @api_endpoint(
        "/list", methods=["GET"], type="http_stream", response_model=Technology, summary="List all technologies"
    )
    async def get_technologies(self, domain: str = None, target_id: str = None):
        async for technology in self.root._get_assets(type="Technology", domain=domain, target_id=target_id):
            yield Technology(**technology)

    @api_endpoint("/list/{host}", methods=["GET"], summary="Get all the technologies on a given host")
    async def get_technologies_for_host(self, host: str) -> list[Technology]:
        return [Technology(**t) async for t in self.root._get_assets(type="Technology", host=host)]

    @api_endpoint("/summarize", methods=["GET"], summary="List hosts for each technology in the database")
    async def get_technologies_summary(self, domain: str = None, target_id: str = None) -> list[dict[str, Any]]:
        technologies = {}
        async for t in self.root._get_assets(
            type="Technology", domain=domain, target_id=target_id, fields=["technology", "host", "last_seen"]
        ):
            technology = t["technology"]
            host = t["host"]
            last_seen = t["last_seen"]
            try:
                existing = technologies[technology]
                existing["last_seen"] = max(last_seen, existing["last_seen"])
                existing["hosts"].add(host)
            except KeyError:
                technologies[technology] = {"last_seen": last_seen, "hosts": {host}}
        technologies = [
            {"technology": t, "last_seen": v["last_seen"], "hosts": sorted(v["hosts"])}
            for t, v in technologies.items()
        ]
        # sort technologies by number of hosts, in reverse order
        technologies.sort(key=lambda x: len(x["hosts"]), reverse=True)
        return technologies

    @api_endpoint(
        "/list_brief",
        methods=["GET"],
        summary="Get all the active technologies for a given domain or target",
        mcp=True,
    )
    async def get_technologies_brief(self, domain: str = None, target_id: str = None) -> dict[str, int]:
        technologies = {}
        async for asset in self.parent._get_assets(
            domain=domain, target_id=target_id, fields=["technologies", "host"]
        ):
            for technology in asset.get("technologies", []):
                try:
                    technologies[technology] += 1
                except KeyError:
                    technologies[technology] = 1
        technologies = dict(sorted(technologies.items(), key=lambda x: x[1], reverse=True))
        return technologies

    @api_endpoint(
        "/search/{technology}",
        methods=["GET"],
        type="http_stream",
        response_model=Technology,
        summary="Search for a technology",
    )
    async def search_technology(self, technology: str, domain: str = None, target_id: str = None):
        async for technology in self.root._get_assets(
            type="Technology",
            search=technology,
            domain=domain,
            target_id=target_id,
            sort=[("last_seen", -1)],
        ):
            yield Technology(**technology)

    async def handle_event(self, event, asset):
        """
        When a new TECHNOLOGY event comes in, we check if it's been seen before. if not, we raise an activity.
        """
        activities = []
        # get our fields from the asset
        old_technologies = set(getattr(asset, "technologies", []))
        t = Technology(
            technology=event.data_json["technology"],
            host=event.host,
            port=event.port,
            netloc=event.netloc,
            last_seen=event.timestamp,
        )
        # insert the technology into the database
        await self._update_or_insert_technology(t)
        # make an activity if the technology is new
        if t.technology not in old_technologies:
            asset.technologies = sorted(old_technologies | {t.technology})
            detail = {"technology": t.technology, "host": t.host}
            activity = self.make_activity(
                type="NEW_TECHNOLOGY",
                description=f"New technology discovered on [bold]{event.host}[/bold]: [[COLOR]{t.technology}[/COLOR]]",
                detail=detail,
                event=event,
            )
            activities.append(activity)
        return activities

    async def compute_stats(self, asset, statistics):
        technologies = getattr(asset, "technologies", [])
        technology_stats = statistics.get("technologies", {})
        for technology in technologies:
            try:
                technology_stats[technology] += 1
            except KeyError:
                technology_stats[technology] = 1
        technology_stats = dict(sorted(technology_stats.items(), key=lambda x: x[1], reverse=True))
        statistics["technologies"] = technology_stats

    async def refresh(self, asset, events_by_type):
        """
        Refresh technologies for an asset (typically run after an archive)
        """
        technologies = set()
        for event in events_by_type.get("TECHNOLOGY", []):
            technologies.add(event.data_json["technology"])

        old_technologies = set(getattr(asset, "technologies", []))
        new_technologies = set(technologies)
        discovered_technologies = new_technologies - old_technologies
        removed_technologies = old_technologies - new_technologies
        asset.technologies = sorted(new_technologies)

        activities = []
        for technology in discovered_technologies:
            activities.append(
                self.make_activity(
                    host=asset.host,
                    type="NEW_TECHNOLOGY",
                    detail={"technology": technology},
                    description=f"New technology discovered on [bold]{asset.host}[/bold]: [[COLOR]{technology}[/COLOR]",
                )
            )
        for technology in removed_technologies:
            activities.append(
                self.make_activity(
                    host=asset.host,
                    type="TECHNOLOGY_REMOVED",
                    detail={"technology": technology},
                    description=f"Technology no longer detected on [bold]{asset.host}[/bold]: [[COLOR]{technology}[/COLOR]",
                )
            )
            if asset.host:
                # archive the technologies
                await self.collection.update_many(
                    {"type": "Technology", "technology": technology, "host": asset.host},
                    {"$set": {"archived": True}},
                )
        return activities

    async def _update_or_insert_technology(self, t: Technology):
        query = {"type": "Technology", "technology": t.technology, "host": t.host, "port": t.port}
        # check if the technology already exists
        existing_technology = await self.collection.find_one(query, {"last_seen": 1})
        if existing_technology:
            last_seen = max(existing_technology["last_seen"], t.last_seen)
            # if it exists, update the last_seen field
            await self.collection.update_one(query, {"$set": {"last_seen": last_seen, "archived": False}})
        else:
            # if it doesn't exist, insert it
            await self.collection.insert_one(t.model_dump())
