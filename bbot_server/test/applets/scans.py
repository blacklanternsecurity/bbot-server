async def scans_test(self):
    # run a bbot scan
    for event in self.scan1_events:
        await self.io.create_event(event)

    targets = await self.io.get_targets()
    assert targets
    assert len(targets) == 1
