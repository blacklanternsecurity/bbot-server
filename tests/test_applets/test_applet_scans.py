import json
import pytest
import asyncio
from pathlib import Path
from contextlib import suppress

from bbot_server import BBOTServer
from bbot_server.errors import BBOTServerValueError
from bbot_server.modules.targets.targets_models import CreateTarget

from ..conftest import INGEST_PROCESSING_DELAY, log


# make sure ad-hoc ingestion of a BBOT scan creates an associated scan run in the database
async def test_scan_run_adhoc(bbot_server, bbot_events):
    bbot_server = await bbot_server(needs_watchdog=True)

    activities = []

    async def watch_activities():
        async for activity in bbot_server.tail_activities():
            activities.append(activity)

    activity_task = asyncio.create_task(watch_activities())

    # we shouldn't have any scan runs yet
    scans = [s async for s in bbot_server.get_scans()]
    assert len(scans) == 0

    scan1_events, scan2_events = bbot_events

    # insert the first event
    for event in scan1_events[:1]:
        await bbot_server.insert_event(event)

    # wait for events to be processed
    await asyncio.sleep(INGEST_PROCESSING_DELAY)

    scans = [s async for s in bbot_server.get_scans()]
    assert len(scans) == 1
    scan = scans[0]
    assert scan.status == "RUNNING"
    assert scan.name == "scan1"

    assert [a.type for a in activities] == ["SCAN_STATUS"]
    assert activities[0].detail["scan_status"] == "RUNNING"

    # insert the rest of the events
    for event in scan1_events[1:]:
        await bbot_server.insert_event(event)

    # wait for events to be processed
    for _ in range(120):
        scans = [s async for s in bbot_server.get_scans()]

        scan_activities = [a for a in activities if a.type.startswith("SCAN_")]
        scan_statuses = [a.detail["scan_status"] for a in scan_activities]

        if (
            len(scans) == 1
            and scans[0].status == "FINISHED"
            and [s.type for s in scan_activities] == ["SCAN_STATUS", "SCAN_STATUS"]
            and [s.detail["scan_status"] for s in scan_activities] == ["RUNNING", "FINISHED"]
        ):
            break

        await asyncio.sleep(0.5)
    else:
        assert False, f"Scan did not finish. Scan activities: {scan_activities}, Scan statuses: {scan_statuses}"

    activity_task.cancel()
    with suppress(asyncio.CancelledError):
        await activity_task


@pytest.mark.skip(reason="Requires agents module shelved in Postgres migration")
async def test_scan_with_invalid_preset(bbot_server, bbot_agent):
    """
    Test that a scan with an invalid preset surfaces the error to the user
    """
    bbot_server = await bbot_server(needs_agent=True, needs_watchdog=True)

    preset = await bbot_server.create_preset(
        preset={"name": "preset1", "description": "preset1 description", "modules": ["invalid"]}
    )
    target = CreateTarget(name="target1", target=["127.0.0.1"])
    target = await bbot_server.create_target(target)
    await bbot_server.start_scan(name="scan1", preset_id=preset.id, target_id=target.id)

    for _ in range(30):
        activities = [a async for a in bbot_server.list_activities(type="SCAN_STATUS")]
        if any(a.detail["scan_status"] == "FAILED" for a in activities):
            break
        await asyncio.sleep(0.5)
    else:
        assert False, "Scan did not fail successfully"


@pytest.mark.skip(reason="Requires agents module shelved in Postgres migration")
async def test_basic_scan_run(bbot_server):
    """
    A basic scan run, with an agent. Makes sure the scan runs start to finish and reports its statuses correctly
    """
    bbot_server = await bbot_server(needs_agent=True, needs_watchdog=True)

    events = []

    async def watch_events():
        async for event in bbot_server.tail_events():
            events.append(event)

    event_task = asyncio.create_task(watch_events())

    # wait for agent to be ready
    for _ in range(120):
        agents = await bbot_server.get_agents()
        log.info(f"Waiting for agent to be ready: agents: {agents}")
        if len(agents) == 1 and agents[0].status == "READY":
            break
        await asyncio.sleep(0.5)
    else:
        assert False, "Agent did not become ready"

    target = CreateTarget(
        name="target1", target=["127.0.0.2"], seeds=["127.0.0.1"], blacklist=["127.0.0.3"], strict_dns_scope=True
    )
    target = await bbot_server.create_target(target)
    preset = await bbot_server.create_preset(
        preset={"name": "preset1", "description": "preset1 description", "scan_name": "teh_scan"}
    )
    await bbot_server.start_scan(target_id=target.id, preset_id=preset.id)

    # wait for scan to finish
    for _ in range(120):
        scans = [a async for a in bbot_server.get_scans()]
        scan_status_finished = len(scans) == 1 and scans[0].status == "FINISHED"

        scan_status_activities = [a async for a in bbot_server.list_activities(type="SCAN_STATUS")]
        scan_statuses = [a.detail["scan_status"] for a in scan_status_activities]
        scan_status_match = scan_statuses == [
            "STARTING",
            "RUNNING",
            "FINISHING",
            "FINISHED",
        ]

        if scan_status_finished and scan_status_match:
            break

        await asyncio.sleep(0.5)
    else:
        scan_status_activities_json = json.dumps([a.model_dump() for a in scan_status_activities], indent=2)
        scans_json = json.dumps([s.model_dump() for s in scans], indent=2)
        assert False, (
            f"Scan runs didn't finish correctly. Scan statuses: {scan_status_activities_json}, Scans: {scans_json}"
        )

    scan_events = [e for e in events if e.type == "SCAN"]
    assert len(scan_events) == 2
    for scan_event in scan_events:
        assert scan_event.data_json["name"] == "teh_scan"
        assert scan_event.data_json["target"]["target"] == ["127.0.0.2"]
        assert scan_event.data_json["target"]["seeds"] == ["127.0.0.1"]
        assert scan_event.data_json["target"]["blacklist"] == ["127.0.0.3"]
        assert scan_event.data_json["target"]["strict_dns_scope"] == True

    ip_events = [e for e in events if e.type == "IP_ADDRESS"]
    assert "127.0.0.1" in [e.data for e in ip_events]

    for _ in range(120):
        # wait for agent to be ready again
        agent_statuses = [a async for a in bbot_server.list_activities(type="AGENT_STATUS")]
        agent_statuses = [a.detail["status"] for a in agent_statuses]
        agent_status_match = agent_statuses == ["ONLINE", "READY", "BUSY", "READY"]

        # agent should be ready again
        agents = await bbot_server.get_agents()
        agent_status_match_2 = len(agents) == 1 and agents[0].status == "READY"

        print(f"Agent statuses: {agent_statuses}, Agents: {agents}")

        if agent_status_match and agent_status_match_2:
            break

        await asyncio.sleep(0.5)
    else:
        assert False, f"Agent did not become ready again. Agent statuses: {agent_statuses}, Agents: {agents}"

    # get scans brief
    scans = await bbot_server.get_scans_brief()
    assert len(scans) == 1
    assert scans[0]["name"] == "teh_scan"
    assert scans[0]["target"]["name"] == "target1"
    assert scans[0]["preset"]["name"] == "preset1"

    event_task.cancel()
    with suppress(asyncio.CancelledError):
        await event_task


@pytest.mark.skip(reason="Requires presets module shelved in Postgres migration")
async def test_queued_scan_cancellation(bbot_server):
    """
    Here we start a scan without an agent, so we have a queued scan in limbo

    Then we cancel the scan, which should remove it from the queue
    """
    bbot_server = await bbot_server()

    target = CreateTarget(name="target1", target=["evilcorp.com"])
    target = await bbot_server.create_target(target)
    preset = await bbot_server.create_preset(preset={"name": "preset1", "description": "preset1 description"})
    scan = await bbot_server.start_scan(name="scan1", target_id=target.id, preset_id=preset.id)

    scans = [s async for s in bbot_server.get_scans()]
    assert len(scans) == 1
    assert scans[0].status == "QUEUED"

    await bbot_server.cancel_scan(id=scan.id)

    scans = [s async for s in bbot_server.get_scans()]
    assert len(scans) == 1
    assert scans[0].status == "ABORTED"


@pytest.mark.skip(reason="Requires agents module shelved in Postgres migration")
async def test_running_scan_cancellation(bbot_agent, bbot_watchdog):
    """
    Here we start a scan with an agent, so we have a running scan

    Then we cancel the scan, and make sure the cleanup etc. happens properly
    """
    # we have to use the HTTP interface here because we can only cancel a scan through the REST API
    bbot_server = BBOTServer(interface="http")
    await bbot_server.setup()

    infinite_module_dir = Path(__file__).parent.parent / "bbot_modules"

    # start scan
    target = CreateTarget(name="target1", target=["evilcorp.com"])
    target = await bbot_server.create_target(target)
    preset = await bbot_server.create_preset(
        preset={
            "name": "preset1",
            "description": "preset1 description",
            "modules": ["infinite"],
            "module_dirs": [str(infinite_module_dir)],
        }
    )
    scan = await bbot_server.start_scan(name="scan1", target_id=target.id, preset_id=preset.id)

    # wait for agent to pick it up
    for _ in range(120):
        scans = [s async for s in bbot_server.get_scans()]
        if len(scans) == 1 and scans[0].status == "RUNNING":
            break
        await asyncio.sleep(0.5)
    else:
        raise Exception("Scan run did not start")

    # wait 5 seconds
    await asyncio.sleep(5.0)

    # make sure the scan run is still running
    scans = [s async for s in bbot_server.get_scans()]
    assert len(scans) == 1
    assert scans[0].status == "RUNNING"

    # cancel the scan
    await bbot_server.cancel_scan(id=scan.id)

    # wait until the scan is cancelled
    for _ in range(120):
        scans = [s async for s in bbot_server.get_scans()]
        if len(scans) == 1 and scans[0].status == "ABORTED":
            break
        await asyncio.sleep(0.5)
    else:
        assert False, f"Scan run did not abort properly. Scans: {scans}"

    # cancelling the scan again should raise an error
    with pytest.raises(BBOTServerValueError):
        await bbot_server.cancel_scan(id=scan.id)

    # make sure the agent is still running and ready to pick up the next scan
    for _ in range(120):
        agents = await bbot_server.get_agents()
        if len(agents) == 1 and agents[0].status == "READY":
            break
        await asyncio.sleep(0.5)
    else:
        assert False, f"Agent did not become ready again. Agents: {agents}"
