async def events_test(self):
    """
    Basic tests CRUD tests for events, making sure we can insert and delete data properly
    """

    # run a bbot scan
    for event in self.scan1_events:
        events = await self.io.get_events()
        await self.io.create_event(event)

    # make sure the data is there
    scans = await self.io.get_scans()
    assert len(scans) == 1
    events = await self.io.get_events()
    assert len(events) == 11
    subdomains = await self.io.get_subdomains()
    assert len(subdomains) == 3
    assert sorted(subdomains) == [
        "asdf.blacklanternsecurity.com",
        "blacklanternsecurity.com",
        "www.blacklanternsecurity.com",
    ]

    # retrieve a event by a single id
    events = await self.io.get_event("DNS_NAME:1e57014aa7b0715bca68e4f597204fc4e1e851fc")
    assert len(events) == 2

    # run a bbot scan
    for event in self.scan2_events:
        await self.io.create_event(event)

    # make sure we have data from both scans
    scans = await self.io.get_scans()
    assert len(scans) == 2
    events = await self.io.get_events()
    assert len(events) == 22
    subdomains = await self.io.get_subdomains()
    assert len(subdomains) == 4
    assert sorted(subdomains) == [
        "api.blacklanternsecurity.com",
        "asdf.blacklanternsecurity.com",
        "blacklanternsecurity.com",
        "www.blacklanternsecurity.com",
    ]

    # retrieve a event by a single id
    events = await self.io.get_event("DNS_NAME:1e57014aa7b0715bca68e4f597204fc4e1e851fc")
    assert len(events) == 4

    # make sure events match perfectly after being inserted and retrieved from the database
    output_events = await self.io.get_events()
    assert set(self.scan1_events + self.scan2_events) == set(output_events)

    subdomain_summary = await self.io.get_subdomain_summary()
    assert subdomain_summary == {
        "api.blacklanternsecurity.com": {"DNS_NAME": 1, "DNS_NAME_UNRESOLVED": 1},
        "asdf.blacklanternsecurity.com": {"DNS_NAME": 1, "DNS_NAME_UNRESOLVED": 1},
        "blacklanternsecurity.com": {
            "DNS_NAME": 4,
            "HTTP_RESPONSE": 2,
            "OPEN_TCP_PORT": 2,
            "URL": 2,
            "URL_UNVERIFIED": 2,
        },
        "www.blacklanternsecurity.com": {"DNS_NAME": 2},
    }
