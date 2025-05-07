import pytest
import asyncio
from pathlib import Path
from contextlib import suppress

from bbot_server import BBOTServer
from bbot_server.errors import BBOTServerNotFoundError

from ..conftest import INGEST_PROCESSING_DELAY


# make sure ad-hoc ingestion of a BBOT scan creates an associated scan run in the database
async def test_scan_run_adhoc(bbot_server, bbot_events):
    bbot_server = await bbot_server(needs_watchdog=True)

    activities = []

    async def watch_activities():
        async for activity in bbot_server.tail_activities():
            activities.append(activity)

    activity_task = asyncio.create_task(watch_activities())

    # we shouldn't have any scan runs yet
    scan_runs = await bbot_server.get_scan_runs()
    assert len(scan_runs) == 0

    scan1_events, scan2_events = bbot_events

    # insert the first event
    for event in scan1_events[:1]:
        await bbot_server.insert_event(event)

    # wait for events to be processed
    await asyncio.sleep(INGEST_PROCESSING_DELAY)

    scan_runs = await bbot_server.get_scan_runs()
    assert len(scan_runs) == 1
    scan_run = scan_runs[0]
    assert scan_run.status == "RUNNING"
    assert scan_run.name == "scan1"

    assert [a.type for a in activities] == ["SCAN_STATUS"]
    assert activities[0].detail["scan_status"] == "RUNNING"

    # insert the rest of the events
    for event in scan1_events[1:]:
        await bbot_server.insert_event(event)

    # wait for events to be processed
    for _ in range(120):
        scan_runs = await bbot_server.get_scan_runs()
        if len(scan_runs) == 1 and scan_runs[0].status == "FINISHED":
            break
        await asyncio.sleep(0.5)
    else:
        assert False, "Scan run did not finish"

    assert [a.type for a in activities if a.type.startswith("SCAN_")] == ["SCAN_STATUS", "SCAN_STATUS"]
    assert [a.detail["scan_status"] for a in activities if a.type.startswith("SCAN_")] == ["RUNNING", "FINISHED"]

    activity_task.cancel()
    with suppress(asyncio.CancelledError):
        await activity_task


async def test_basic_scan_run(bbot_server):
    """
    A basic scan run, with an agent. Makes sure the scan runs start to finish and reports its statuses correctly
    """
    bbot_server = await bbot_server(needs_agent=True, needs_watchdog=True)

    # wait for agent to be ready
    for _ in range(120):
        agents = await bbot_server.get_agents()
        if len(agents) == 1 and agents[0].status == "READY":
            break
        await asyncio.sleep(0.5)
    else:
        assert False, "Agent did not become ready"

    target = await bbot_server.create_target(name="target1", seeds=["127.0.0.1"])
    scan = await bbot_server.create_scan(name="scan1", target_id=target.id)
    await bbot_server.start_scan(scan_id=scan.id)

    # wait for scan to finish
    for _ in range(120):
        scan_runs = await bbot_server.get_scan_runs()
        scan_status_finished = len(scan_runs) == 1 and scan_runs[0].status == "FINISHED"

        scan_statuses = [a async for a in bbot_server.get_activities(type="SCAN_STATUS")]
        scan_statuses = [a.detail["scan_status"] for a in scan_statuses]
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
        assert False, f"Scan run did not finish. Scan statuses: {scan_statuses}, Scan runs: {scan_runs}"

    for _ in range(120):
        # wait for agent to be ready again
        agent_statuses = [a async for a in bbot_server.get_activities(type="AGENT_STATUS")]
        agent_statuses = [a.detail["status"] for a in agent_statuses]
        agent_status_match = agent_statuses == ["ONLINE", "READY", "BUSY", "READY"]

        # agent should be ready again
        agents = await bbot_server.get_agents()
        agent_status_match_2 = len(agents) == 1 and agents[0].status == "READY"

        if agent_status_match and agent_status_match_2:
            break

        await asyncio.sleep(0.5)
    else:
        assert False, f"Agent did not become ready again. Agent statuses: {agent_statuses}, Agents: {agents}"


async def test_queued_scan_cancellation(bbot_server):
    """
    Here we start a scan without an agent, so we have a queued scan in limbo

    Then we cancel the scan, which should remove it from the queue
    """
    bbot_server = await bbot_server()

    target = await bbot_server.create_target(name="target1", seeds=["evilcorp.com"])
    scan = await bbot_server.create_scan(name="scan1", target_id=target.id)
    await bbot_server.start_scan(scan_id=scan.id)

    scan_runs = await bbot_server.get_scan_runs()
    assert len(scan_runs) == 1
    assert scan_runs[0].status == "QUEUED"

    await bbot_server.cancel_scan(scan_run_id=scan_runs[0].id)

    scan_runs = await bbot_server.get_scan_runs()
    assert len(scan_runs) == 1
    assert scan_runs[0].status == "ABORTED"


async def test_running_scan_cancellation(bbot_server_config, bbot_agent, bbot_watchdog):
    """
    Here we start a scan with an agent, so we have a running scan

    Then we cancel the scan, and make sure the cleanup etc. happens properly
    """
    # we have to use the HTTP interface here because we can only cancel a scan through the REST API
    bbot_server = BBOTServer(interface="http", config=bbot_server_config)
    await bbot_server.setup()

    infinite_module_dir = Path(__file__).parent.parent / "bbot_modules"
    preset = {"modules": ["infinite"], "module_dirs": [str(infinite_module_dir)]}

    # start scan
    target = await bbot_server.create_target(name="target1", seeds=["evilcorp.com"])
    scan = await bbot_server.create_scan(name="scan1", target_id=target.id, preset=preset)
    await bbot_server.start_scan(scan_id=scan.id)

    # wait for agent to pick it up
    for _ in range(120):
        scan_runs = await bbot_server.get_scan_runs()
        if len(scan_runs) == 1 and scan_runs[0].status == "RUNNING":
            break
        await asyncio.sleep(0.5)
    else:
        raise Exception("Scan run did not start")

    # wait 5 seconds
    await asyncio.sleep(5.0)

    # make sure the scan run is still running
    scan_runs = await bbot_server.get_scan_runs()
    assert len(scan_runs) == 1
    assert scan_runs[0].status == "RUNNING"

    # cancel the scan
    await bbot_server.cancel_scan(scan_run_id=scan_runs[0].id)

    # wait until the scan is cancelled
    for _ in range(120):
        scan_runs = await bbot_server.get_scan_runs()
        if len(scan_runs) == 1 and scan_runs[0].status == "ABORTED":
            break
        await asyncio.sleep(0.5)
    else:
        assert False, f"Scan run did not abort properly. Scan runs: {scan_runs}"

    # cancelling the scan again should raise an error
    with pytest.raises(BBOTServerNotFoundError, match="Scan isn't running on agent"):
        await bbot_server.cancel_scan(scan_run_id=scan_runs[0].id)

    # make sure the agent is still running and ready to pick up the next scan
    agents = await bbot_server.get_agents()
    assert len(agents) == 1
    assert agents[0].status == "READY"

    activities = [a async for a in bbot_server.get_activities(type="SCAN_STATUS")]
    print(activities)
