from typing import Annotated, Any
from fastapi import Query

from bbot_server.models.base import AssetQuery
from bbot_server.assets import CustomAssetFields
from bbot_server.applets.base import BaseApplet, api_endpoint
from bbot_server.modules.technologies.technologies_models import (
    TechnologyQuery,
    Technology,
)


# add one field: 'technologies' to the main asset model
class TechnologiesFields(CustomAssetFields):
    technologies: Annotated[list[str], "indexed", "indexed-text"] = []  # noqa: F821


class TechnologiesApplet(BaseApplet):
    name = "Technologies"
    watched_events = ["TECHNOLOGY"]
    description = "technologies discovered during scans"
    attach_to = "assets"
    model = Technology

    @api_endpoint(
        "/get/{id}",
        methods=["GET"],
        summary="Get a technology by ID. This returns a single technology for a single host.",
        mcp=True,
    )
    async def get_technology(self, id: str) -> Technology:
        return Technology(**(await self.root._get_asset(type="Technology", id=id)))

    @api_endpoint(
        "/list", methods=["GET"], type="http_stream", response_model=Technology, summary="List all technologies", mcp=True
    )
    async def list_technologies(
        self,
        domain: str = None,
        host: str = None,
        technology: Annotated[str, Query(description="filter by technology (must match exactly)")] = None,
        search: Annotated[
            str, Query(description="A human-friendly text search (will be ANDed with other filters)")
        ] = None,
        target_id: Annotated[str, Query(description="filter by target (can be either name or ID)")] = None,
        archived: Annotated[bool, Query(description="whether to include archived technologies")] = False,
        active: Annotated[bool, Query(description="whether to include active (non-archived) technologies")] = True,
        sort: Annotated[list[str], Query(description="fields to sort by")] = ["-last_seen"],
    ):
        query = TechnologyQuery(
            technology=technology,
            search=search,
            domain=domain,
            host=host,
            target_id=target_id,
            archived=archived,
            active=active,
            sort=sort,
        )
        async for technology in query.mongo_iter(self):
            yield Technology(**technology)

    @api_endpoint("/query", methods=["POST"], type="http_stream", response_model=dict, summary="Query technologies", mcp=True)
    async def query_technologies(self, query: TechnologyQuery | None = None):
        """
        Advanced querying of technologies. Choose your own filters and fields.
        """
        async for technology in query.mongo_iter(self):
            yield technology

    @api_endpoint("/count", methods=["POST"], summary="Count technologies", mcp=True)
    async def count_technologies(self, query: TechnologyQuery | None = None) -> int:
        """
        Same as query_technologies, except only returns the count
        """
        return await query.mongo_count(self)

    @api_endpoint("/summarize", methods=["GET"], summary="List hosts for each technology in the database", mcp=True)
    async def get_technologies_summary(
        self,
        domain: Annotated[str, Query(description="filter by domain (subdomains included)")] = None,
        host: Annotated[str, Query(description="filter by host")] = None,
        technology: Annotated[str, Query(description="filter by technology (must match exactly)")] = None,
        search: Annotated[str, Query(description="search for a technology (fuzzy match)")] = None,
        target_id: Annotated[str, Query(description="filter by target (can be either name or ID)")] = None,
    ) -> list[dict[str, Any]]:
        """
        Get a summary of technologies, e.g.:

        [
            {
                "technology": "cpe:/a:apache:http_server:2.4.12",
                "last_seen": 1718275200,
                "hosts": ["t1.tech.evilcorp.com", "t2.tech.evilcorp.com"],
            }
        ]
        """
        # TODO: use mongo aggregation pipeline?
        technologies = {}
        # Build kwargs, filtering out None values so they don't conflict with MISSING defaults
        query_kwargs = {
            k: v
            for k, v in {
                "domain": domain,
                "host": host,
                "technology": technology,
                "search": search,
                "target_id": target_id,
            }.items()
            if v is not None
        }
        async for t in self.query_technologies(fields=["technology", "host", "last_seen"], **query_kwargs):
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
        summary="Get all active technologies by domain or target id.",
        mcp=True,
    )
    async def get_technologies_brief(
        self,
        domain: Annotated[str, Query(description="filter by domain (subdomains included)")] = None,
        host: Annotated[str, Query(description="filter by host")] = None,
        target_id: Annotated[str, Query(description="filter by target (can be either name or ID)")] = None,
    ) -> dict[str, int]:
        technologies = {}
        query = AssetQuery(
            type="Asset",
            domain=domain,
            host=host,
            target_id=target_id,
            fields=["technologies", "host"],
        )
        async for asset in query.mongo_iter(self):
            for technology in asset.get("technologies", []):
                technologies[technology] = technologies.get(technology, 0) + 1
        technologies = dict(sorted(technologies.items(), key=lambda x: x[1], reverse=True))
        return technologies

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
        # inherit scope from the parent asset so as to make sure that target_id filtering works
        if asset and hasattr(asset, "scope"):
            t.scope = asset.scope
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
                    description=f"New technology discovered on [bold]{asset.host}[/bold]: [[COLOR]{technology}[/COLOR]]",
                )
            )
        for technology in removed_technologies:
            activities.append(
                self.make_activity(
                    host=asset.host,
                    type="TECHNOLOGY_REMOVED",
                    detail={"technology": technology},
                    description=f"Technology no longer detected on [bold]{asset.host}[/bold]: [[COLOR]{technology}[/COLOR]]",
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
            await self.root._insert_asset(t.model_dump())
