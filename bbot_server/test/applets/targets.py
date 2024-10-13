async def targets_test(self, gen_scan_data):
    scan1_events, scan2_events = await gen_scan_data()

    # Complete the first scan
    for event in scan1_events:
        await self.io.create_event(event)

    # There should be one target after the first scan event
    targets = await self.io.get_targets()
    assert targets
    assert len(targets) == 1

    # Create the second scan
    for event in scan2_events:
        await self.io.create_event(event)

    # There should still be only one target after both scans
    targets = await self.io.get_targets()
    assert len(targets) == 2
