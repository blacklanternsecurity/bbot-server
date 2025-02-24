import uuid
import asyncio
from contextlib import suppress
from typing import Annotated, Any
from bbot_server.models.base import BaseBBOTServerModel

from bbot_server.applets.agents import AgentsApplet
from bbot_server.applets.scan_runs import ScanRunsApplet
from bbot_server.applets.yara_rules import YaraRulesApplet

from bbot_server.applets._base import BaseApplet, api_endpoint


class Scan(BaseBBOTServerModel):
    __tablename__ = "scans"

    name: Annotated[str, "indexed", "unique"]
    id: Annotated[str, "indexed", "unique"] = ""
    target: list[str] = []
    whitelist: list[str] = []
    blacklist: list[str] = []
    preset: dict[str, Any] = {}

    def make_preset(self):
        from bbot import Preset

        preset = Preset(**self.preset)
        target_preset = Preset(*self.target, whitelist=self.whitelist, blacklist=self.blacklist, scan_name=self.name)
        preset.merge(target_preset)
        return preset


class ScansApplet(BaseApplet):
    name = "Scans"
    description = "scans"
    include_apps = [AgentsApplet, ScanRunsApplet, YaraRulesApplet]
    model = Scan

    async def setup(self):
        self.scan_watch_task = asyncio.create_task(self.watch_scan_queue())

    async def watch_scan_queue(self):
        while True:
            ready_agents = await self.get_online_agents(status="READY")
            if not ready_agents:
                self.log.debug(f"No ready agents found")
                await asyncio.sleep(1)
                continue
            selected_agent = ready_agents[0]
            self.log.info(f"Selected agent {selected_agent.name} for scan")
            # read just one scan from the nats queue
            scan_preset = await self.message_queue.get("bbot.queued_scans", "scan_queue_watcher")
            await self.agents.send_message(selected_agent.id, "start_scan", kwargs={"preset": scan_preset})
            await self.emit_activity(
                type="SCAN_DISPATCHED",
                description=f"Scan [[dark_orange]{scan_preset.scan_name}[/dark_orange]] sent to agent [[dark_orange]{selected_agent.name}[/dark_orange]]",
            )

    @api_endpoint("/", methods=["GET"], summary="List scans")
    async def get_scans(self) -> list[Scan]:
        cursor = self.collection.find()
        scans = await cursor.to_list(length=None)
        scans = [Scan(**scan) for scan in scans]
        return scans

    @api_endpoint("/{name}", methods=["GET"], summary="Get a single scan by its name")
    async def get_scan(self, name: str) -> Scan:
        scan = await self.collection.find_one({"name": name})
        if scan is None:
            return
        return Scan(**scan)

    @api_endpoint("/create", methods=["POST"], summary="Create a new scan")
    async def create_scan(self, scan: Scan) -> Scan:
        scan.id = str(uuid.uuid4())
        await self.collection.insert_one(scan.model_dump())
        return scan

    @api_endpoint("/edit/{name}", methods=["POST"], summary="Update a scan")
    async def edit_scan(self, name: str, scan: Scan) -> Scan:
        await self.collection.update_one({"name": name}, {"$set": scan.model_dump()})
        return scan

    @api_endpoint("/{name}", methods=["DELETE"], summary="Delete a scan based on its name")
    async def delete_scan(self, name: str) -> None:
        await self.collection.delete_one({"name": name})

    @api_endpoint("/{name}/start", methods=["POST"], summary="Start a scan")
    async def start_scan(self, name: str) -> None:
        scan = await self.get_scan(name)
        if scan is None:
            return
        preset = scan.make_preset()
        await self.message_queue.publish(preset, "bbot.queued_scans")
        await self.emit_activity(
            type="SCAN_QUEUED",
            description=f"Scan [[dark_orange]{name}[/dark_orange]] queued",
        )

    async def cleanup(self):
        self.scan_watch_task.cancel()
        with suppress(asyncio.CancelledError):
            await self.scan_watch_task
