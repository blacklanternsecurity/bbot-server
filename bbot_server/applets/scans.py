import uuid
from pydantic import UUID4, Field
from typing import Annotated, Any

from bbot import Preset
from bbot_server.models.base import BaseBBOTServerModel

from bbot_server.applets.agents import AgentsApplet
from bbot_server.applets.targets import TargetsApplet, Target
from bbot_server.applets.scan_runs import ScanRunsApplet
from bbot_server.applets.yara_rules import YaraRulesApplet

from bbot_server.applets._base import BaseApplet, api_endpoint


class Scan(BaseBBOTServerModel):
    __tablename__ = "scans"

    name: Annotated[str, "indexed", "unique"]
    id: Annotated[UUID4, "indexed", "unique"] = Field(default_factory=uuid.uuid4)
    target: Annotated[UUID4, "indexed"]
    preset: dict[str, Any] = {}

    def make_preset(self):
        preset = Preset(**self.preset)
        target_preset = Preset(*self.target, whitelist=self.whitelist, blacklist=self.blacklist, scan_name=self.name)
        preset.merge(target_preset)
        return preset


class ScansApplet(BaseApplet):
    name = "Scans"
    description = "scans"
    include_apps = [TargetsApplet, AgentsApplet, ScanRunsApplet, YaraRulesApplet]
    model = Scan

    @api_endpoint("/", methods=["GET"], summary="Get a single scan by its name")
    async def get_scan(self, name: str = "", id: UUID4 = None) -> Scan:
        if (not name) and (not id):
            raise self.BBOTValueError("Either name or id must be provided")
        query = {}
        if name:
            query["name"] = name
        elif id is not None:
            query["id"] = str(id)
        scan = await self.collection.find_one(query)
        if scan is None:
            return
        return Scan(**scan)

    @api_endpoint("/create", methods=["POST"], summary="Create a new scan")
    async def create_scan(self, name: str, target: UUID4, preset: dict[str, Any] = {}) -> Scan:
        if await self.get_target(id=target) is None:
            raise self.BBOTNotFoundError("Target not found")
        scan = Scan(name=name, target=target, preset=preset)
        await self.collection.insert_one(scan.model_dump())
        return scan

    @api_endpoint("/{id}", methods=["PATCH"], summary="Update a scan by its id")
    async def update_scan(self, id: UUID4, scan: Scan) -> Scan:
        scan.id = id
        await self.collection.update_one({"id": str(id)}, {"$set": scan.model_dump()})
        return scan

    @api_endpoint("/{id}", methods=["DELETE"], summary="Delete a scan by its id")
    async def delete_scan(self, id: UUID4) -> None:
        await self.collection.delete_one({"id": str(id)})

    @api_endpoint("/list", methods=["GET"], summary="List scans")
    async def get_scans(self) -> list[Scan]:
        cursor = self.collection.find()
        scans = await cursor.to_list(length=None)
        scans = [Scan(**scan) for scan in scans]
        return scans

    @api_endpoint("/start/{id}", methods=["POST"], summary="Start a scan")
    async def start_scan(self, id: str) -> None:
        scan = await self.get_scan(id=id)
        if scan is None:
            raise self.BBOTNotFoundError("Scan not found")
        target = await self.get_target(id=scan.target)
        preset = Preset(*target.target, whitelist=target.whitelist, blacklist=target.blacklist, **scan.preset)
        preset_dict = preset.bake().to_dict(include_target=True)
        await self.message_queue.publish(preset_dict, "bbot.queued_scans")
        await self.emit_activity(
            type="SCAN_QUEUED",
            description=f"Scan [[dark_orange]{scan.name}[/dark_orange]] queued",
        )
