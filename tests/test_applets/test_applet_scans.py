import asyncio


async def test_applet_scans(bbot_server):
    bbot_server = await bbot_server(needs_agent=True)

    scans = await bbot_server.get_scans()
    assert scans == []

    # first, create a target
    target = await bbot_server.create_target(
        name="target1",
        description="target1 description",
        target=["localhost"],
    )

    # then create a scan
    scan1 = await bbot_server.create_scan(
        name="scan1",
        target=target.id,
        preset={"config": {"web": {"user_agent": "BBOT User Agent"}}},
    )

    scans = await bbot_server.get_scans()
    assert len(scans) == 1
    scan = scans[0]
    assert scan.name == "scan1"
    assert scan.target_id == target.id
    assert scan.preset == {"config": {"web": {"user_agent": "BBOT User Agent"}}}

    scan2 = await bbot_server.create_scan(
        name="scan2",
        target=target.id,
        preset={"config": {"web": {"user_agent": "BBOT User Agent 2"}}},
    )

    scans = await bbot_server.get_scans()
    assert len(scans) == 2
    scan = scans[1]
    assert scan.name == "scan2"
    assert scan.target_id == target.id
    assert scan.preset == {"config": {"web": {"user_agent": "BBOT User Agent 2"}}}

    # delete scan1
    await bbot_server.delete_scan(scan1.id)
    scans = await bbot_server.get_scans()
    assert len(scans) == 1
    scan = scans[0]
    assert scan.name == "scan2"

    # edit scan2
    target2 = await bbot_server.create_target(
        name="target2",
        description="target2 description",
        target=["127.0.0.1"],
    )
    scan2.name = "scan2_edited"
    scan2.target_id = target2.id
    scan2.preset = {"config": {"web": {"user_agent": "BBOT User Agent 3"}}}
    await bbot_server.update_scan(scan2.id, scan2)
    scans = await bbot_server.get_scans()
    assert len(scans) == 1
    scan = scans[0]
    assert scan.id == scan2.id
    assert scan.name == "scan2_edited"
    assert scan.target_id == target2.id
    assert scan.preset == {"config": {"web": {"user_agent": "BBOT User Agent 3"}}}

    # make sure an agent is running
    assert len(await bbot_server.get_agents()) == 1

    # tail asset activities
    activities = []

    async def tail_activities():
        async for activity in bbot_server.tail_assets():
            activities.append(activity)

    asyncio.create_task(tail_activities())

    # start scan2
    await bbot_server.start_scan(scan2.id)

    for _ in range(100):
        activity_types = [a.type for a in activities]
        if activity_types == ["AGENT_CONNECTED", "SCAN_QUEUED", "SCAN_SENT", "SCAN_STARTED", "SCAN_FINISHED"]:
            break
        await asyncio.sleep(0.1)
    else:
        print(f"ACTIVITIES: {activity_types}")
        assert False, f"Scan didn't finish properly. Activities: {activities}"
