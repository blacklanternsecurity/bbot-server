from typing import Any
from pydantic import UUID4


from bbot_server.utils.misc import timestamp_to_human

from bbot_server.applets.agents import AgentsApplet
from bbot_server.applets.scans.scan_runs import ScanRunsApplet
from bbot_server.applets.scans.yara_rules import YaraRulesApplet

from bbot_server.models.activity import Activity
from bbot_server.applets._base import BaseApplet, api_endpoint
from bbot_server.applets.scans.scan_models import ScanResponse, ScanDBEntry


class ScansApplet(BaseApplet):
    name = "Scans"
    description = "scans"
    watched_events = ["SCAN"]
    include_apps = [AgentsApplet, ScanRunsApplet, YaraRulesApplet]
    model = ScanDBEntry

    async def handle_event(self, event, asset=None):
        scan_id = event.data_json["id"]
        try:
            scan_run = await self.get_scan(id=scan_id)
        except self.BBOTServerNotFoundError:
            return []

        if "finished_at" in event.data_json:
            update_op = {"$set": {"finished_at": event.data_json["finished_at"]}}
            activity = "SCAN_FINISHED"
            human_finished_at = timestamp_to_human(event.data_json["finished_at"])
            description = f"Scan [[COLOR]{scan_run.name}[/COLOR]] finished at {human_finished_at}"
        else:
            update_op = {"$set": {"started_at": event.data_json["started_at"]}}
            activity = "SCAN_STARTED"
            human_started_at = timestamp_to_human(event.data_json["started_at"])
            description = f"Scan [[COLOR]{scan_run.name}[/COLOR]] started at {human_started_at}"

        await self.collection.update_one({"id": scan_id}, update_op)
        activity = Activity(type=activity, description=description)
        return [activity]

    @api_endpoint("/", methods=["GET"], summary="Get a single scan by its name")
    async def get_scan(self, name: str = "", id: str = None) -> ScanDBEntry:
        if (not name) and (not id):
            raise self.BBOTServerError("Either name or id must be provided")
        query = {}
        if name:
            query["name"] = name
        elif id is not None:
            query["id"] = str(id)
        scan = await self.collection.find_one(query)
        if scan is None:
            raise self.BBOTServerNotFoundError("Scan not found")
        target_id = scan.pop("target_id")
        target = await self.root.get_target(id=target_id)
        scan["target"] = target
        return ScanResponse(**scan)

    @api_endpoint("/create", methods=["POST"], summary="Create a new scan")
    async def create_scan(self, name: str, target: UUID4, preset: dict[str, Any] = {}) -> ScanDBEntry:
        if await self.root.get_target(id=target) is None:
            raise self.BBOTServerNotFoundError("Target not found")
        scan = ScanDBEntry(name=name, target_id=target, preset=preset)
        await self.collection.insert_one(scan.model_dump())
        return scan

    @api_endpoint("/{id}", methods=["PATCH"], summary="Update a scan by its id")
    async def update_scan(self, id: UUID4, scan: ScanDBEntry) -> ScanDBEntry:
        scan.id = id
        await self.collection.update_one({"id": str(id)}, {"$set": scan.model_dump()})
        return scan

    @api_endpoint("/{id}", methods=["DELETE"], summary="Delete a scan by its id")
    async def delete_scan(self, id: UUID4) -> None:
        await self.collection.delete_one({"id": str(id)})

    @api_endpoint("/list", methods=["GET"], summary="List scans")
    async def get_scans(self) -> list[ScanDBEntry]:
        cursor = self.collection.find()
        scans = await cursor.to_list(length=None)
        scans = [ScanDBEntry(**scan) for scan in scans]
        return scans

    @api_endpoint("/start/{scan_id}", methods=["POST"], summary="Start a scan")
    async def start_scan(self, scan_id: str, agent_id: str = None) -> None:
        scan_run = await self.runs.new_run(scan_id, agent_id)
        return scan_run
