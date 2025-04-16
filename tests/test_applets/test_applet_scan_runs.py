import asyncio
from contextlib import suppress


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
    await asyncio.sleep(0.5)

    scan_runs = await bbot_server.get_scan_runs()
    assert len(scan_runs) == 1
    scan_run = scan_runs[0]
    assert scan_run.status == "RUNNING"
    assert scan_run.name == "scan1"

    assert [a.type for a in activities] == ["SCAN_STARTED"]

    # insert the rest of the events
    for event in scan1_events[1:]:
        await bbot_server.insert_event(event)

    # wait for events to be processed
    await asyncio.sleep(0.5)

    scan_runs = await bbot_server.get_scan_runs()
    assert len(scan_runs) == 1
    scan_run = scan_runs[0]
    assert scan_run.status == "FINISHED"

    assert [a.type for a in activities if a.type.startswith("SCAN_")] == ["SCAN_STARTED", "SCAN_FINISHED"]

    activity_task.cancel()
    with suppress(asyncio.CancelledError):
        await activity_task
