from datetime import datetime


async def scans_test(self, gen_scan_data):
    scan1_events, scan2_events = await gen_scan_data()

    # start with only the first event of the scan
    event = scan1_events[0]
    await self.io.create_event(event)

    # it should be a scan event
    events = await self.io.get_events()
    assert len(events) == 1
    event = events[0]
    assert event.type == "SCAN"

    # a scan object should be created automatically
    scans = await self.io.get_scans()
    assert len(scans) == 1
    scan = scans[0]
    # it shouldn't be completed yet
    assert scan.status == "RUNNING"
    assert isinstance(scan.validated.started_at, datetime)
    assert scan.finished_at == None

    # finish inserting the rest of the events
    for event in scan1_events[1:]:
        await self.io.create_event(event)

    # there should now be two scan events
    events = await self.io.get_events()
    scan_events = [e for e in events if e.type == "SCAN"]
    assert len(scan_events) == 2

    # but there should still be only one scan
    scans = await self.io.get_scans()
    assert len(scans) == 1
    scan = scans[0]
    # and it should be marked as completed
    assert scan.status == "FINISHED"
    assert isinstance(scan.validated.started_at, datetime)
    assert isinstance(scan.validated.finished_at, datetime)

    # now we'll insert a second scan
    for event in scan2_events:
        await self.io.create_event(event)

    # there should now be four scan events
    events = await self.io.get_events()
    scan_events = [e for e in events if e.type == "SCAN"]
    assert len(scan_events) == 4

    # and two scan objects
    scans = await self.io.get_scans()
    assert len(scans) == 2
    for scan in scans:
        s = await self.io.get_scan(scan.id)
        assert s == scan
