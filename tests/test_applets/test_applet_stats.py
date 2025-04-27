import asyncio


# test to make sure you can filter assets by target
async def test_applet_stats(bbot_server, bbot_events):
    bbot_server = await bbot_server(needs_watchdog=True)

    target1 = await bbot_server.create_target(
        whitelist=["evilcorp.com"],
        blacklist=["www.evilcorp.com"],
    )

    # ingest BBOT events
    for scan_events in bbot_events:
        for e in scan_events:
            await bbot_server.insert_event(e)

    # wait for events to be processed
    await asyncio.sleep(1)

    # global stats
    stats = await bbot_server.get_stats()
    # 80: www.evilcorp.com, www2.evilcorp.com
    # 443: api.evilcorp.com
    assert stats == {
        "dns_links": {
            "A": 11,
            "AAAA": 1,
            "CNAME": 1,
            "TXT": 6,
        },
        "open_ports": {
            80: 2,
            443: 1,
        },
    }

    # by target
    stats = await bbot_server.get_stats(target_id=target1.id)
    assert stats == {
        "dns_links": {
            "A": 7,
            "CNAME": 1,
            "TXT": 6,
        },
        "open_ports": {
            80: 1,
            443: 1,
        },
    }

    # by domain
    stats = await bbot_server.get_stats(domain="www2.evilcorp.com")
    assert stats == {
        "dns_links": {
            "A": 2,
        },
        "open_ports": {
            80: 1,
        },
    }
