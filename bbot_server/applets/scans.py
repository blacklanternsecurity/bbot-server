import random
import asyncio
import traceback
from pydantic import UUID4
from pymongo import ASCENDING
from contextlib import suppress
from pymongo.errors import DuplicateKeyError

from bbot.core.helpers.names_generator import random_name
from bbot.constants import (
    get_scan_status_name,
    get_scan_status_code,
    SCAN_STATUS_FAILED,
    SCAN_STATUS_QUEUED,
    SCAN_STATUS_ABORTED,
    SCAN_STATUS_FINISHED,
)

from bbot_server.applets.agents import AgentsApplet
from bbot_server.applets.presets import PresetsApplet
from bbot_server.applets.targets import TargetsApplet
from bbot_server.applets.yara_rules import YaraRulesApplet

from bbot_server.models.scan_models import Scan
from bbot_server.models.target_models import Target
from bbot_server.models.preset_models import Preset
from bbot_server.models.activity_models import Activity
from bbot_server.applets._base import BaseApplet, api_endpoint


class ScansApplet(BaseApplet):
    name = "Scans"
    description = "scans"
    watched_events = ["SCAN"]
    watched_activities = ["SCAN_STATUS"]
    include_apps = [AgentsApplet, YaraRulesApplet, TargetsApplet, PresetsApplet]
    model = Scan

    async def setup(self):
        if self.is_main_server:
            # this task will start scans when agents are ready
            self.scan_watch_task = self.create_task(self.start_scans_loop())
        return True, ""

    @api_endpoint("/get/{id}", methods=["GET"], summary="Get a single scan by its name or ID")
    async def get_scan(self, id: str) -> Scan:
        scan = await self.collection.find_one({"$or": [{"id": str(id)}, {"name": str(id)}]})
        if scan is None:
            raise self.BBOTServerNotFoundError("Scan not found")
        return Scan(**scan)

    @api_endpoint("/start", methods=["POST"], summary="Create a new scan")
    async def start_scan(
        self,
        target_id: str,
        preset_id: str,
        name: str = None,
        agent_id: UUID4 = None,
        seed_with_current_assets: bool = False,
    ) -> Scan:
        target = await self.get_target(target_id)
        preset = await self.get_preset(preset_id)
        # if seed_with_current_assets is True, we add all our currently known hosts that match the target
        if seed_with_current_assets:
            seeds = set(target.seeds)
            seeds.update(await self.root.get_hosts(target_id=target_id))
            target.seeds = list(seeds)
        name = name or preset.preset.get("scan_name", None)
        if name is None:
            name = await self.get_available_scan_name()
        scan = Scan(
            name=name,
            target=target,
            preset=preset,
            agent_id=agent_id,
            seed_with_current_assets=seed_with_current_assets,
        )
        try:
            await self.collection.insert_one(scan.model_dump())
        except DuplicateKeyError:
            raise self.BBOTServerValueError(f"Scan with name '{name}' already exists")
        description = f"Scan [[COLOR]{scan.name}[/COLOR]] queued"
        if agent_id is not None:
            agent = await self.get_agent(id=agent_id)
            description += f" on agent [bold]{agent.name}[/bold]"
        await self.emit_activity(
            type="SCAN_QUEUED",
            description=description,
            detail={"scan_id": str(scan.id), "agent_id": agent_id},
        )
        return scan

    @api_endpoint("/list", methods=["GET"], type="http_stream", response_model=Scan, summary="Get all scans")
    async def get_scans(self):
        async for scan in self.collection.find():
            yield Scan(**scan)

    @api_endpoint(
        "/list_brief", methods=["GET"], summary="Get all scans in a brief format (without target info)", mcp=True
    )
    async def get_scans_brief(self):
        return await self.collection.find(
            {}, {"name": 1, "id": 1, "target.name": 1, "preset.name": 1, "_id": 0}
        ).to_list(length=None)

    async def get_available_scan_name(self) -> str:
        """
        Returns a scan name that's guaranteed to not be in use, e.g. "demonic_jimmy"
        """
        valid_name = False
        while not valid_name:
            name = random_name()
            if not await self.collection.find_one({"name": name}):
                valid_name = True
        return name

    @api_endpoint("/queued", methods=["GET"], summary="List queued scans")
    async def get_queued_scans(self) -> list[Scan]:
        # we sort by `created` ascending to get the oldest queued scans first
        cursor = self.collection.find({"status": "QUEUED"}, sort=[("created", ASCENDING)])
        return [Scan(**run) for run in await cursor.to_list(length=None)]

    @api_endpoint("/cancel/{id}", methods=["POST"], summary="Cancel a scan by its name or ID")
    async def cancel_scan(self, scan_id: str, force: bool = False):
        # get the scan
        scan = await self.get_scan(scan_id)

        existing_scan_status_code = get_scan_status_code(getattr(scan, "status_code", SCAN_STATUS_QUEUED))
        if existing_scan_status_code >= SCAN_STATUS_FINISHED:
            raise self.BBOTServerValueError(f"Scan {scan.name} is already finished, skipping")

        mark_aborted = False
        if scan.agent_id is None:
            # if we don't have an agent id, it's probably a queued scan
            self.log.info(f"Scan {scan.name} has no agent id, marking as aborted")
            mark_aborted = True
        else:
            self.log.info(f"Scan {scan.name} is running on agent {scan.agent_id}, checking if it's running")

            # if the agent doesn't exist, we clear the agent from the scan and try again
            try:
                agent = await self.get_agent(id=scan.agent_id)
            except self.BBOTServerNotFoundError:
                self.log.warning(f"Scan's agent no longer exists. Clearing agent from scan")
                await self.collection.update_one({"id": str(scan.id)}, {"$set": {"agent_id": None}})
                return await self.cancel_scan(str(scan.id), force=force)

            # otherwise, we check if the agent is actually running our scan
            if str(agent.current_scan_id) != str(scan.id):
                # if this happens, it means the scan probably is stalled or failed
                mark_aborted = True
                self.log.info(f"Scan isn't running on agent (current_scan_id={agent.current_scan_id})")
            else:
                self.log.info(f"Scan {scan.name} is running on agent {scan.agent_id}, sending cancel command")
                command_result = await self.execute_agent_command(scan.agent_id, "cancel_scan", force=force)
                if command_result.error:
                    self.log.warning(f"Error cancelling scan on agent: {command_result.error}")

        if mark_aborted:
            # if the scan is already aborted, we don't need to do anything
            if scan.status == "ABORTED":
                self.log.info(f"Scan {scan.name} is already aborted, skipping")
                return
            self.log.info(f"Marking {scan.name} as aborted")
            await self.collection.update_one(
                {"id": str(scan.id)}, {"$set": {"status": "ABORTED", "status_code": SCAN_STATUS_ABORTED}}
            )

        await self.emit_activity(
            type="SCAN_STATUS",
            description=f"Scan [[COLOR]{scan.name}[/COLOR]] aborted",
            detail={
                "scan_id": str(scan.id),
                "scan_name": scan.name,
                "scan_status": "ABORTED",
                "scan_status_code": SCAN_STATUS_ABORTED,
                "agent_id": scan.agent_id,
            },
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
                ready_agents = {str(agent.id): agent for agent in await self.get_online_agents(status="READY")}
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
                            # check if agent doesn't exist anymore. if so, we'll clear it from the scan.
                            try:
                                selected_agent = await self.get_agent(str(scan.agent_id))
                            except self.BBOTServerNotFoundError:
                                self.log.warning(f"Scan's agent no longer exists. Clearing agent from scan")
                                await self.collection.update_one({"id": str(scan.id)}, {"$set": {"agent_id": None}})
                                continue

                    self.log.info(f"Selected agent: {selected_agent.name}")

                    # assign the agent to the scan
                    await self.collection.update_one(
                        {"id": str(scan.id)}, {"$set": {"agent_id": str(selected_agent.id)}}
                    )

                    # merge target and preset
                    scan_preset = dict(scan.preset.preset)
                    scan_preset["scan_name"] = scan.name
                    scan_preset["target"] = scan.target.seeds
                    scan_preset["whitelist"] = scan.target.whitelist
                    scan_preset["blacklist"] = scan.target.blacklist
                    config = scan_preset.get("config", {})
                    scope_config = config.get("scope", {})
                    scope_config["strict"] = scan.target.strict_dns_scope
                    config["scope"] = scope_config
                    scan_preset["config"] = config

                    # send the scan to the agent
                    scan_start_response = await self.execute_agent_command(
                        str(selected_agent.id), "start_scan", scan_id=scan.id, preset=scan_preset
                    )
                    if scan_start_response.error:
                        self.log.warning(f"Error sending scan to agent: {scan_start_response.error}")
                        await self.emit_activity(
                            type="SCAN_STATUS",
                            description=f"Scan [[COLOR]{scan.name}[/COLOR]] failed to start",
                            detail={
                                "scan_id": scan.id,
                                "scan_name": scan.name,
                                "agent_id": str(selected_agent.id),
                                "scan_status": "FAILED",
                                "scan_status_code": SCAN_STATUS_FAILED,
                                "error": scan_start_response.error,
                            },
                        )
                        await self.sleep(1)
                        continue

                    await self.emit_activity(
                        type="SCAN_SENT",
                        description=f"Scan [[COLOR]{scan.name}[/COLOR]] sent to agent [[bold]{selected_agent.name}[/bold]]",
                        detail={"scan_id": scan.id, "agent_id": str(selected_agent.id)},
                    )
                    # make the scan as sent
                    await self.collection.update_one({"id": str(scan.id)}, {"$set": {"status": "SENT_TO_AGENT"}})

        except Exception as e:
            self.log.error(f"Error in scans loop: {e}")
            self.log.error(traceback.format_exc())

    async def handle_event(self, event, asset) -> list[Activity]:
        """
        Whenever we get a SCAN event, we create or update the scan in the database.
        """
        scan_dict = event.data_json
        scan_name = scan_dict["name"]
        target = Target(name=f"{scan_name} Target", **scan_dict.pop("target"))
        preset = Preset(preset=scan_dict.pop("preset"))
        scan = Scan(
            target=target,
            preset=preset,
            **scan_dict,
        )
        scan_id = str(scan.id)
        detail = {
            "scan_id": scan_id,
            "scan_name": scan.name,
            "scan_status": scan.status,
            "scan_status_code": scan.status_code,
        }

        try:
            existing_scan = await self.get_scan(scan_id)
        except self.BBOTServerNotFoundError:
            existing_scan = None
        existing_status_code = get_scan_status_code(getattr(existing_scan, "status_code", SCAN_STATUS_QUEUED))
        # if the scan already exists, update it
        if existing_scan:
            # ignore if the new status is at or behind the existing one
            if scan.status_code <= existing_status_code:
                return []
            existing_status = get_scan_status_name(existing_status_code)
            description = f"Scan [[COLOR]{scan.name}[/COLOR]] status changed from [bold]{existing_status}[/bold] to [bold]{scan.status}[/bold]"
            agent_id = getattr(existing_scan, "agent_id", None)
            if agent_id is not None:
                detail["agent_id"] = agent_id
            await self.collection.update_one(
                {"id": scan_id},
                {
                    "$set": {
                        "started_at": scan.started_at,
                        "finished_at": scan.finished_at,
                        "duration": scan.duration,
                        "duration_seconds": scan.duration_seconds,
                    }
                },
            )
            status_changed = await self.update_scan_status(scan_id=scan_id, status_code=scan.status_code)
        # otherwise, assume the scan is starting and create a new run
        else:
            description = f"Scan [[COLOR]{scan.name}[/COLOR]] started"
            await self.collection.insert_one(scan.model_dump())
            status_changed = True

        if status_changed:
            scan_run_activity = Activity(
                type="SCAN_STATUS",
                event=event,
                description=description,
                detail=detail,
            )
            return [scan_run_activity]
        else:
            self.log.debug(f"Scan {scan.name} status not changed, skipping activity")
            return []

    async def update_scan_status(self, scan_id: str, status_code: int):
        status_code = get_scan_status_code(status_code)
        status = get_scan_status_name(status_code)
        result = await self.strict_collection.update_one(
            {"id": scan_id}, {"$set": {"status": status, "status_code": status_code}}
        )
        return result.modified_count > 0

    async def cleanup(self):
        if self.is_main_server:
            self.scan_watch_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.scan_watch_task
