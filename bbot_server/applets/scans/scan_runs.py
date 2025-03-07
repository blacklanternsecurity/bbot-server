import random
import asyncio
from contextlib import suppress

from bbot_server.applets._base import BaseApplet, api_endpoint
from bbot_server.applets.scans.scan_models import ScanRun, ScanDBEntry


class ScanRunsApplet(BaseApplet):
    name = "Runs"
    watched_events = ["SCAN"]
    description = "individual scan runs"
    _route_prefix = "/runs"
    model = ScanRun

    async def setup(self):
        self.scan_watch_task = self.create_task(self.start_scans_loop())

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

    @api_endpoint("/queued", methods=["GET"], summary="List queued scans")
    async def get_queued_scans(self) -> list[ScanRun]:
        cursor = self.collection.find({"status": "QUEUED"})
        return await cursor.to_list(length=None)

    async def new_run(self, scan_id: str, agent_id: str = None) -> ScanRun:
        scan = await self.parent.get_scan(id=scan_id)
        if scan is None:
            raise self.BBOTServerNotFoundError("Scan not found")

        scan_run = self.make_run_from_scan(scan, agent_id)

        await self.collection.insert_one(scan_run.model_dump())
        description = f"Scan [[dark_orange]{scan.name}[/dark_orange]] queued"
        if agent_id is not None:
            agent = await self.parent.get_agent(id=agent_id)
            description += f" on agent [[dark_orange]{agent.name}[/dark_orange]]"
        await self.emit_activity(
            type="SCAN_QUEUED",
            description=description,
            detail={"scan_id": scan_id, "agent_id": agent_id},
        )
        return scan_run

    @api_endpoint("/", methods=["GET"], summary="List individual BBOT scan runs")
    async def get_scan_runs(self) -> list[dict]:
        cursor = self.collection.find()
        scan_runs = []
        for run in await cursor.to_list(length=None):
            scan_runs.append(ScanRun(**run))

        return scan_runs

    def make_run_from_scan(self, scan: ScanDBEntry, agent_id: str = None) -> ScanRun:
        return ScanRun(
            id=scan.id,
            name=scan.name,
            target=scan.target,
            parent_scan_id=scan.id,
            preset=scan.preset,
            agent_id=agent_id,
        )

    async def start_scans_loop(self):
        while True:
            # get all queued scans
            queued_scans = await self.get_queued_scans()
            if not queued_scans:
                await self.sleep(1)
                continue
            # get all alive agents
            alive_agents = {agent.id: agent for agent in await self.parent.get_online_agents()}
            if not alive_agents:
                self.log.warning("No agents are currently connected")
                await self.sleep(1)
                continue
            for scan in queued_scans:
                if scan.agent_id is None:
                    selected_agent = random.choice(list(alive_agents.values()))
                else:
                    try:
                        selected_agent = alive_agents[scan.agent_id]
                    except KeyError:
                        selected_agent = await self.parent.get_agent(id=scan.agent_id)
                        self.log.warning(f"Agent {selected_agent.name} is not online")
                        continue
                await self

    async def cleanup_scan(self):
        self.scan_watch_task.cancel()
        with suppress(asyncio.CancelledError):
            await self.scan_watch_task
