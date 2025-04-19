from typing import Any
from pydantic import UUID4
from contextlib import contextmanager
from pymongo.errors import DuplicateKeyError

from bbot_server.applets.agents import AgentsApplet
from bbot_server.applets.scans.scan_runs import ScanRunsApplet
from bbot_server.applets.scans.yara_rules import YaraRulesApplet

from bbot_server.applets._base import BaseApplet, api_endpoint
from bbot_server.models.scan_models import ScanResponse, ScanDBEntry


class ScansApplet(BaseApplet):
    name = "Scans"
    description = "scans"
    watched_events = ["SCAN"]
    include_apps = [AgentsApplet, ScanRunsApplet, YaraRulesApplet]
    model = ScanDBEntry

    @api_endpoint("/", methods=["GET"], summary="Get a single scan by its name")
    async def get_scan(self, name: str = "", id: str = None) -> ScanResponse:
        if (not name) and (not id):
            raise self.BBOTServerError("Must provide either a scan name or id")
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
    async def create_scan(self, target_id: UUID4, name: str = None, preset: dict[str, Any] = {}) -> ScanDBEntry:
        if await self.root.get_target(id=target_id) is None:
            raise self.BBOTServerNotFoundError("Target not found")
        if name is None:
            name = await self.get_available_scan_name()
        scan = ScanDBEntry(name=name, target_id=target_id, preset=preset)
        with self._handle_duplicate_scan(scan):
            await self.collection.insert_one(scan.model_dump())
        return scan

    @api_endpoint("/{id}", methods=["PATCH"], summary="Update a scan by its id")
    async def update_scan(self, id: UUID4, scan: ScanDBEntry) -> ScanDBEntry:
        existing_scan = await self.get_scan(id=id)
        scan.id = id
        scan.created = existing_scan.created
        scan.modified = self.utc_now()
        with self._handle_duplicate_scan(scan):
            await self.collection.update_one({"id": str(id)}, {"$set": scan.model_dump()})
        return scan

    @api_endpoint("/{id}", methods=["DELETE"], summary="Delete a scan by its id")
    async def delete_scan(self, id: UUID4) -> None:
        # TODO: delete events + refresh assets
        await self.collection.delete_one({"id": str(id)})

    @api_endpoint("/list", methods=["GET"], type="http_stream", response_model=ScanResponse, summary="Get all scans")
    async def get_scans(self):
        for scan_id in await self.collection.distinct("id"):
            yield await self.get_scan(id=scan_id)

    @api_endpoint("/list_brief", methods=["GET"], summary="Get all scans in a brief format (without target info)")
    async def get_scans_brief(self, target_id: UUID4 = None):
        query = {}
        if target_id is not None:
            query["target_id"] = str(target_id)
        scans = await self.collection.find(query).to_list(length=None)
        return [ScanDBEntry(**scan) for scan in scans]

    @api_endpoint("/start/{scan_id}", methods=["POST"], summary="Start a scan")
    async def start_scan(self, scan_id: str, agent_id: str = None) -> None:
        scan_run = await self.runs.new_run(scan_id, agent_id)
        return scan_run

    async def get_available_scan_name(self) -> str:
        """
        Returns a scan name that's guaranteed to not be in use, such as "Scan 1", "Scan 2", etc.
        """
        # Get all existing scan names
        existing_names = await self.collection.distinct("name")
        # Start with "Scan 1" and increment until we find an unused name
        counter = 1
        while f"Scan {counter}" in existing_names:
            counter += 1
        return f"Scan {counter}"

    @contextmanager
    def _handle_duplicate_scan(self, scan: ScanDBEntry):
        try:
            yield
        except DuplicateKeyError as e:
            key_value = e.details["keyValue"]
            if "name" in key_value:
                raise self.BBOTServerValueError(
                    f'Scan with name "{scan.name}" already exists', detail={"name": key_value["name"]}
                )
            raise self.BBOTServerValueError(f"Error creating scan: {e}")
