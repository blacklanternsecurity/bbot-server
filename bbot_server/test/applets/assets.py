async def assets_test(self, gen_scan_data):
    scan1_events, scan2_events = await gen_scan_data()

    # Insert test data
    for event in scan1_events:
        await self.io.create_event(event)

    # GET ASSETS
    assets = await self.io.get_assets()
    assert len(assets) == 14
    assert set(assets) == {
        "1.2.3.4",
        "blacklanternsecurity.com",
        "newdnsstatus.blacklanternsecurity.com",
        "newhttpstatus.blacklanternsecurity.com",
        "portclosed.blacklanternsecurity.com",
        "portopened.blacklanternsecurity.com",
        "resolvedtounresolved.blacklanternsecurity.com",
        "tagadded.blacklanternsecurity.com",
        "tagremoved.blacklanternsecurity.com",
        "technologyadded.blacklanternsecurity.com",
        "technologyremoved.blacklanternsecurity.com",
        "unresolvedtoresolved.blacklanternsecurity.com",
        "vulnadded.blacklanternsecurity.com",
        "www.blacklanternsecurity.com",
    }

    # OPEN PORTS
    basedomain = await self.io.get_asset("blacklanternsecurity.com")
    assert basedomain.open_ports == [443]
    assert len(basedomain.history) == 1
    assert basedomain.history[0].description == "New open port detected: 443"
    www = await self.io.get_asset("www.blacklanternsecurity.com")
    assert www.open_ports == []
    assert len(www.history) == 0
    portopened = await self.io.get_asset("portopened.blacklanternsecurity.com")
    assert portopened.open_ports == [8443]
    assert len(portopened.history) == 1
    assert portopened.history[0].description == "New open port detected: 8443"

    # insert scan2 events
    for event in scan2_events:
        await self.io.create_event(event)

    # Test get_assets() after second scan
    assets = await self.io.get_assets()
    assert len(assets) == 16
    assert set(assets) == {
        "1.2.3.4",
        "1.2.3.0/24",
        "blacklanternsecurity.com",
        "newasset.blacklanternsecurity.com",
        "newdnsstatus.blacklanternsecurity.com",
        "newhttpstatus.blacklanternsecurity.com",
        "portclosed.blacklanternsecurity.com",
        "portopened.blacklanternsecurity.com",
        "resolvedtounresolved.blacklanternsecurity.com",
        "tagadded.blacklanternsecurity.com",
        "tagremoved.blacklanternsecurity.com",
        "technologyadded.blacklanternsecurity.com",
        "technologyremoved.blacklanternsecurity.com",
        "unresolvedtoresolved.blacklanternsecurity.com",
        "vulnadded.blacklanternsecurity.com",
        "www.blacklanternsecurity.com",
    }

    # OPEN PORTS
    basedomain = await self.io.get_asset("blacklanternsecurity.com")
    assert basedomain.open_ports == [443]
    assert len(basedomain.history) == 1
    assert basedomain.history[0].description == "New open port detected: 443"
    portopened = await self.io.get_asset("portopened.blacklanternsecurity.com")
    assert portopened.open_ports == [8080, 8443]
    assert len(portopened.history) == 2
    assert portopened.history[0].description == "New open port detected: 8443"
    assert portopened.history[1].description == "New open port detected: 8080"
