async def _test_scans(self):
    input_events = []

    # run a bbot scan
    async for event in self.ingest_bbot_scan(self.dns_mock_1):
        input_events.append(event)

    # events = await self.io.get_events()
    # print(events)
    # scans = await self.io.get_scans()
    # print(scans)
    # targets = await self.io.get_targets()
    # print(targets)
