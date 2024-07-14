async def _test_events(self):
    """
    Basic tests CRUD tests for events, making sure we can insert and delete data properly
    """

    input_events = []

    # run a bbot scan
    async for event in self.ingest_bbot_scan(self.dns_mock_1):
        input_events.append(event)

    # make sure the data is there
    scans = await self.io.get_scans()
    assert len(scans) == 1
    events = await self.io.get_events()
    assert len(events) == 11
    subdomains = await self.io.get_subdomains()
    assert len(subdomains) == 3
    assert "blacklanternsecurity.com" in subdomains
    assert "www.blacklanternsecurity.com" in subdomains
    assert "asdf.blacklanternsecurity.com" in subdomains

    # run another scan
    async for event in self.ingest_bbot_scan(self.dns_mock_2):
        input_events.append(event)

    # make sure we have data from both scans
    scans = await self.io.get_scans()
    assert len(scans) == 2
    events = await self.io.get_events()
    assert len(events) == 22
    subdomains = await self.io.get_subdomains()
    assert len(subdomains) == 4
    assert "blacklanternsecurity.com" in subdomains
    assert "api.blacklanternsecurity.com" in subdomains
    assert "www.blacklanternsecurity.com" in subdomains
    assert "asdf.blacklanternsecurity.com" in subdomains

    # make sure events match perfectly after being inserted and retrieved from the database
    output_events = await self.io.get_events()
    assert set(input_events) == set(output_events)
