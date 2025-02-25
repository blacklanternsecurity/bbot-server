import asyncio


async def test_applet_scans(bbot_server):
    from bbot_server.applets.scans import Scan

    bbot_server = await bbot_server(needs_agent=True)

    scans = await bbot_server.get_scans()
    assert scans == []

    # first, create a target
    target = await bbot_server.create_target(
        name="target1",
        description="target1 description",
        target=["localhost"],
    )

    # create a scan
    scan1 = await bbot_server.create_scan(
        name="scan1",
        target=target.id,
        preset={"config": {"web": {"user_agent": "BBOT User Agent"}}},
    )

    scans = await bbot_server.get_scans()
    assert len(scans) == 1
    assert scans[0].name == "scan1"
    assert scans[0].target == target.id
    assert scans[0].preset == {"config": {"web": {"user_agent": "BBOT User Agent"}}}

    scan2 = await bbot_server.create_scan(
        name="scan2",
        target=target.id,
        preset={"config": {"web": {"user_agent": "BBOT User Agent 2"}}},
    )

    scans = await bbot_server.get_scans()
    assert len(scans) == 2
    assert scans[1].name == "scan2"
    assert scans[1].target == target.id
    assert scans[1].preset == {"config": {"web": {"user_agent": "BBOT User Agent 2"}}}

    # delete scan1
    await bbot_server.delete_scan(scan1.id)
    scans = await bbot_server.get_scans()
    assert len(scans) == 1
    assert scans[0].name == "scan2"

    # edit scan2
    target2 = await bbot_server.create_target(
        name="target2",
        description="target2 description",
        target=["127.0.0.1"],
    )
    scan2.name = "scan2_edited"
    scan2.target = target2.id
    scan2.preset = {"config": {"web": {"user_agent": "BBOT User Agent 3"}}}
    await bbot_server.update_scan(scan2.id, scan2)
    scans = await bbot_server.get_scans()
    assert len(scans) == 1
    assert scans[0].id == scan2.id
    assert scans[0].name == "scan2_edited"
    assert scans[0].target == target2.id
    assert scans[0].preset == {"config": {"web": {"user_agent": "BBOT User Agent 3"}}}

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

    # wait for scan to finish
    await asyncio.sleep(1)

    # check if scan2 finished
    print(activities)
