import pytest
import asyncio
import logging

from bbot_server.errors import BBOTServerValueError

log = logging.getLogger("bbot_server.test_applet_scans")


async def test_applet_scans(bbot_server):
    bbot_server = await bbot_server(needs_agent=True, needs_api=True)

    # tail activities + events
    activities = []
    events = []

    async def tail_activities():
        async for activity in bbot_server.tail_activities(n=10):
            activities.append(activity)

    async def tail_events():
        async for event in bbot_server.tail_events(n=10):
            events.append(event)

    asyncio.create_task(tail_activities())
    asyncio.create_task(tail_events())

    scans = [s async for s in bbot_server.get_scans()]
    assert scans == []

    # first, create a target
    target = await bbot_server.create_target(
        name="target1",
        description="target1 description",
        seeds=["localhost"],
    )

    # then create a scan
    scan1 = await bbot_server.create_scan(
        name="scan1",
        target_id=target.id,
        preset={"config": {"web": {"user_agent": "BBOT User Agent"}}},
    )

    scans = [s async for s in bbot_server.get_scans()]
    assert len(scans) == 1
    scan = scans[0]
    assert scan.name == "scan1"
    assert scan.target_id == target.id
    assert scan.preset == {"config": {"web": {"user_agent": "BBOT User Agent"}}}

    scan2 = await bbot_server.create_scan(
        name="scan2",
        target_id=target.id,
        preset={"config": {"web": {"user_agent": "BBOT User Agent 2"}}},
    )

    scans = [s async for s in bbot_server.get_scans()]
    assert len(scans) == 2
    scan = scans[1]
    assert scan.name == "scan2"
    assert scan.target_id == target.id
    assert scan.preset == {"config": {"web": {"user_agent": "BBOT User Agent 2"}}}

    # delete scan1
    await bbot_server.delete_scan(scan1.id)
    scans = [s async for s in bbot_server.get_scans()]
    assert len(scans) == 1
    scan = scans[0]
    assert scan.name == "scan2"

    # edit scan2
    target2 = await bbot_server.create_target(
        name="target2",
        description="target2 description",
        seeds=["127.0.0.1"],
    )
    scan2.name = "scan2_edited"
    scan2.target_id = target2.id
    scan2.preset = {"config": {"web": {"user_agent": "BBOT User Agent 3"}}}
    await bbot_server.update_scan(scan2.id, scan2)
    scans = [s async for s in bbot_server.get_scans()]
    assert len(scans) == 1
    scan = scans[0]
    assert scan.id == scan2.id
    assert scan.name == "scan2_edited"
    assert scan.target_id == target2.id
    assert scan.preset == {"config": {"web": {"user_agent": "BBOT User Agent 3"}}}

    # make sure an agent is running
    all_agents = await bbot_server.get_agents()
    assert len(all_agents) == 1
    online_agents = await bbot_server.get_online_agents()
    assert len(online_agents) == 1, f"No online agents (all agents: {all_agents} / activities: {activities})"

    # start scan2
    await bbot_server.start_scan(scan2.id)

    for _ in range(100):
        activity_types = [a.type for a in activities]
        event_types = [e.type for e in events]
        if activity_types == [
            "AGENT_CONNECTED",
            "TARGET_CREATED",
            "TARGET_CREATED",
            "SCAN_QUEUED",
            "SCAN_SENT",
            "SCAN_STARTED",
            "SCAN_FINISHED",
        ]:
            if event_types == ["SCAN", "SCAN"]:
                break
        await asyncio.sleep(0.1)
    else:
        assert False, (
            f"Scan didn't finish properly. Activities: {[a.type for a in activities]}, Events: {[e.type for e in events]}"
        )


async def test_scan_auto_naming(bbot_server):
    bbot_server = await bbot_server()

    target = await bbot_server.create_target(
        name="target1",
        description="target1 description",
        seeds=["localhost"],
    )

    scan1 = await bbot_server.create_scan(target_id=target.id)
    assert scan1.name == "Scan 1"
    scan2 = await bbot_server.create_scan(target_id=target.id)
    assert scan2.name == "Scan 2"
    scan3 = await bbot_server.create_scan(target_id=target.id)
    assert scan3.name == "Scan 3"

    with pytest.raises(BBOTServerValueError, match='Scan with name "Scan 3" already exists'):
        await bbot_server.create_scan(name="Scan 3", target_id=target.id)

    with pytest.raises(BBOTServerValueError, match='Scan with name "Scan 2" already exists'):
        await bbot_server.update_scan(scan3.id, scan2)
