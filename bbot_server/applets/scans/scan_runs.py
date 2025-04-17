import random
import asyncio
import traceback
from contextlib import suppress

from bbot.core.helpers.names_generator import random_name

from bbot_server.models.activity_models import Activity
from bbot_server.applets._base import BaseApplet, api_endpoint
from bbot_server.models.scan_models import ScanRun, ScanDBEntry


class ScanRunsApplet(BaseApplet):
    name = "Runs"
    watched_events = ["SCAN"]
    watched_activities = ["SCAN_STATUS"]
    description = "individual scan runs"
    _route_prefix = "/runs"
    model = ScanRun

    async def setup(self):
        if self.is_main_server:
            # this task will start scans when agents are ready
            self.scan_watch_task = self.create_task(self.start_scans_loop())

    async def handle_activity(self, activity: Activity) -> list[Activity]:
        scan_id = activity.detail["scan_id"]
        scan_status = activity.detail["scan_status"]
        self.collection.update_one({"id": scan_id}, {"$set": {"status": scan_status}})

    async def handle_scan(self, event) -> list[Activity]:
        """
        Whenever we get a new scan event,
        """
        scan_run = ScanRun(**event.data_json)
        scan_run_id = str(scan_run.id)
        detail = {"scan_id": scan_run_id}

        existing_scan_run = await self.collection.find_one({"id": scan_run_id})
        # if the scan run already exists, update it
        if existing_scan_run:
            status = "STARTED" if scan_run.status == "RUNNING" else scan_run.status
            activity_type = f"SCAN_{status}"
            description = (
                f"Scan [{scan_run.name}] status changed from {existing_scan_run['status']} to {scan_run.status}"
            )
            description_colored = f"Scan [[COLOR]{scan_run.name}[/COLOR]] status changed from {existing_scan_run['status']} to {scan_run.status}"
            agent_id = existing_scan_run.get("agent_id", None)
            if agent_id is not None:
                detail["agent_id"] = agent_id
            await self.collection.update_one(
                {"id": scan_run_id},
                {
                    "$set": {
                        "status": scan_run.status,
                        "started_at": scan_run.started_at,
                        "finished_at": scan_run.finished_at,
                    }
                },
            )
        # otherwise, assume the scan is starting and create a new run
        else:
            activity_type = "SCAN_STARTED"
            description = f"Scan [{scan_run.name}] started"
            description_colored = f"Scan [[COLOR]{scan_run.name}[/COLOR]] started"
            await self.collection.insert_one(scan_run.model_dump())

        scan_run_activity = Activity(
            type=activity_type,
            event=event,
            description=description,
            description_colored=description_colored,
            detail=detail,
        )
        return [scan_run_activity]

    @api_endpoint("/queued", methods=["GET"], summary="List queued scans")
    async def get_queued_scans(self) -> list[ScanRun]:
        cursor = self.collection.find({"status": "QUEUED"})
        return [ScanRun(**run) for run in await cursor.to_list(length=None)]

    @api_endpoint("/cancel/{id}", methods=["POST"], summary="Cancel a scan run by its id")
    async def cancel_scan(self, scan_run_id: str, force: bool = False):
        scan_run = await self.collection.find_one({"id": str(scan_run_id)}, {"id": 1, "agent_id": 1, "name": 1})
        if scan_run is None:
            raise self.BBOTServerNotFoundError("Scan run not found")
        agent_id = scan_run.get("agent_id", None)
        # if we don't have an agent id, it's a queued scan
        if agent_id is None:
            await self.collection.update_one({"id": str(scan_run_id)}, {"$set": {"status": "CANCELLED"}})
        else:
            await self.root.cancel_scan(agent_id, "cancel_scan", scan_run_id=scan_run_id, force=force)
            if force:
                await self.emit_activity(
                    type="SCAN_STATUS",
                    description=f"Scan [[COLOR]{scan_run.name}[/COLOR]] cancelled",
                    detail={
                        "scan_id": scan_run_id,
                        "scan_name": scan_run.name,
                        "scan_status": "CANCELLED",
                        "agent_id": agent_id,
                    },
                )

    async def new_run(self, scan_id: str, agent_id: str = None) -> ScanRun:
        scan = await self.parent.get_scan(id=scan_id)
        if scan is None:
            raise self.BBOTServerNotFoundError("Scan not found")

        scan_run = self.make_run_from_scan(scan, agent_id)

        await self.collection.insert_one(scan_run.model_dump())
        description = f"Scan [[COLOR]{scan.name}[/COLOR]] queued"
        if agent_id is not None:
            agent = await self.parent.get_agent(id=agent_id)
            description += f" on agent [[COLOR]{agent.name}[/COLOR]]"
        await self.emit_activity(
            type="SCAN_QUEUED",
            description=description,
            detail={"scan_id": scan_id, "agent_id": agent_id},
        )
        return scan_run

    @api_endpoint("/{id}", methods=["GET"], summary="Get a scan run by its id")
    async def get_scan_run(self, scan_run_id: str) -> ScanRun:
        scan_run = await self.collection.find_one({"id": str(scan_run_id)})
        if scan_run is None:
            raise self.BBOTServerNotFoundError("Scan run not found")
        return ScanRun(**scan_run)

    @api_endpoint("/", methods=["GET"], summary="List individual BBOT scan runs")
    async def get_scan_runs(self) -> list[ScanRun]:
        cursor = self.collection.find()
        scan_runs = []
        for run in await cursor.to_list(length=None):
            scan_runs.append(ScanRun(**run))
        return scan_runs

    def make_run_from_scan(self, scan: ScanDBEntry, agent_id: str = None) -> ScanRun:
        random_scan_name = random_name()
        return ScanRun(
            id=str(scan.id),
            name=f"{scan.name} ({random_scan_name})",
            target=scan.target,
            parent_scan_id=scan.id,
            preset=scan.preset,
            agent_id=agent_id,
        )

    async def start_scans_loop(self):
        try:
            while True:
                # get all queued scans
                queued_scans = await self.get_queued_scans()
                if not queued_scans:
                    await self.sleep(1)
                    continue
                self.log.info(f"Found {len(queued_scans):,} queued scans")
                # get all alive agents
                ready_agents = {str(agent.id): agent for agent in await self.parent.get_online_agents(status="READY")}
                if not ready_agents:
                    self.log.warning("No agents are currently ready")
                    await self.sleep(1)
                    continue
                self.log.info(f"Found {len(ready_agents):,} ready agents")
                for scan in queued_scans:
                    # find a suitable agent for the scan
                    if scan.agent_id is None:
                        selected_agent = random.choice(list(ready_agents.values()))
                    else:
                        try:
                            selected_agent = ready_agents[str(scan.agent_id)]
                        except KeyError:
                            self.log.warning(f"Agent {scan.agent_id} was selected for a scan, but it is not online")
                            try:
                                selected_agent = await self.parent.get_agent(id=scan.agent_id)
                            except self.BBOTServerNotFoundError as e:
                                self.log.warning(f"Error sending scan to selected agent: {e}")
                                continue

                    self.log.info(f"Selected agent: {selected_agent.name}")

                    # assign the agent to the scan
                    await self.collection.update_one(
                        {"id": str(scan.id)}, {"$set": {"agent_id": str(selected_agent.id)}}
                    )

                    # send the scan to the agent
                    scan_start_response = await self.parent.execute_command(
                        str(selected_agent.id), "start_scan", scan_run=scan.model_dump()
                    )
                    if scan_start_response.error:
                        self.log.warning(f"Error sending scan to agent: {scan_start_response.error}")
                        await self.sleep(1)
                        continue

                    await self.emit_activity(
                        type="SCAN_SENT",
                        description=f"Scan [[COLOR]{scan.name}[/COLOR]] sent to agent [[COLOR]{selected_agent.name}[/COLOR]]",
                        detail={"scan_id": scan.id, "agent_id": str(selected_agent.id)},
                    )
                    # make the scan as sent
                    await self.collection.update_one({"id": str(scan.id)}, {"$set": {"status": "SENT_TO_AGENT"}})

        except Exception as e:
            self.log.error(f"Error in scans loop: {e}")
            self.log.error(traceback.format_exc())

    async def cleanup(self):
        if self.is_main_server:
            self.scan_watch_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.scan_watch_task
