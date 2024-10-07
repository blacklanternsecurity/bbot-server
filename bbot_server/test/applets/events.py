async def events_test(self):
    """
    Basic CRUD tests for events, making sure we can insert and retrieve data properly
    """
    # run a bbot scan
    for event in self.scan1_events:
        await self.io.create_event(event)

    # make sure the data is there
    scans = await self.io.get_scans()
    assert len(scans) == 1
    events = await self.io.get_events()
    assert len(events) == 12

    # retrieve an event by a single id
    events = await self.io.get_events_by_id("DNS_NAME:1e57014aa7b0715bca68e4f597204fc4e1e851fc")
    assert len(events) == 2

    for event in events:
        result = await self.io.get_event_by_uuid(event.uuid)
        assert result.get_data() == "blacklanternsecurity.com"

    # run a second bbot scan
    for event in self.scan2_events:
        await self.io.create_event(event)

    # make sure we have data from both scans
    scans = await self.io.get_scans()
    assert len(scans) == 2
    events = await self.io.get_events()
    assert len(events) == 24

    # retrieve an event by a single id
    # this one is for blacklanternsecurity.com
    events = await self.io.get_events_by_id("DNS_NAME:1e57014aa7b0715bca68e4f597204fc4e1e851fc")
    assert len(events) == 4

    for event in events:
        result = await self.io.get_event_by_uuid(event.uuid)
        assert result.get_data() == "blacklanternsecurity.com"

    # make sure events match perfectly after being inserted and retrieved from the database
    output_events = await self.io.get_events()
    assert set(self.scan1_events + self.scan2_events) == set(output_events)
