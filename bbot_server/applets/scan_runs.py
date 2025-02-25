import asyncio
from datetime import datetime
from typing import Any, Union
from contextlib import suppress

from bbot_server.models.base import BaseBBOTServerModel
from bbot_server.applets._base import BaseApplet, api_endpoint


class ScanRun(BaseBBOTServerModel):
    __tablename__ = "scan_runs"

    id: str
    name: str
    status: str
    target: dict[str, Any]
    preset: dict[str, Any]
    started_at: datetime
    finished_at: Union[datetime, None] = None
    duration_seconds: Union[float, None] = None
    duration: Union[str, None] = None


class ScanRunsApplet(BaseApplet):
    name = "Runs"
    watched_events = ["SCAN"]
    description = "individual scan runs"
    _route_prefix = "/runs"
    model = ScanRun

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

    # async def ingest_event(self, asset, event) -> list[AssetActivity]:
    #     scan_run = ScanRun(**event.data_json)
    #     activity_type = f"SCAN_{scan_run.status}"

    #     existing_scan_run = await self.collection.find_one({"id": scan_run.id})
    #     if existing_scan_run:
    #         description = (
    #             f'Scan [{scan_run.name}] status changed from {existing_scan_run["status"]} to {scan_run.status}'
    #         )
    #         description_colored = f'Scan [[dark_orange]{scan_run.name}[/dark_orange]] status changed from {existing_scan_run["status"]} to {scan_run.status}'
    #         await self.collection.update_one({"id": scan_run.id}, {"$set": scan_run.model_dump()})
    #     else:
    #         description = f"Scan [{scan_run.name}] started"
    #         description_colored = f"Scan [[dark_orange]{scan_run.name}[/dark_orange]] started"
    #         await self.collection.insert_one(scan_run.model_dump())

    #     scan_run_activity = AssetActivity(
    #         type=activity_type,
    #         event=event,
    #         description=description,
    #         description_colored=description_colored,
    #     )
    #     return [scan_run_activity]

    @api_endpoint("/", methods=["GET"], summary="List individual BBOT scan runs")
    async def get_scan_runs(self) -> list[dict]:
        cursor = self.collection.find()
        scan_runs = []
        for run in await cursor.to_list(length=None):
            scan_runs.append(ScanRun(**run))

        return scan_runs

    async def cleanup(self):
        self.scan_watch_task.cancel()
        with suppress(asyncio.CancelledError):
            await self.scan_watch_task
