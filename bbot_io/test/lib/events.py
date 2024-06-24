async def _test_events(self):
    """
    Basic tests CRUD tests for events, making sure we can insert and delete data properly
    """

    dns_mock_1 = dict(self.base_dns_mock)
    dns_mock_1.update(
        {
            "asdf.blacklanternsecurity.com": {
                "A": ["127.0.0.1"],
            }
        }
    )

    dns_mock_2 = dict(self.base_dns_mock)
    dns_mock_2.update(
        {
            "api.blacklanternsecurity.com": {
                "A": ["127.0.0.1"],
            }
        }
    )

    input_events = []

    # run a bbot scan
    async for event in self.run_bbot_scan(dns_mock_1):
        input_events.append(event)
        await self.io.insert_event(event)

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
    async for event in self.run_bbot_scan(dns_mock_2):
        input_events.append(event)
        await self.io.insert_event(event)

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
