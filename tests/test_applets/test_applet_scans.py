from tests.test_applets.base import BaseAppletTest


async def test_scans_applet(bbot_server):
    from bbot_server.applets.scans import Scan

    bbot_server = await bbot_server()

    scans = await bbot_server.get_scans()
    assert scans == []

    # create a scan
    scan1_obj = Scan(
        name="scan1",
        target=["localhost"],
        whitelist=["127.0.0.1", "evilcorp.com"],
        blacklist=["127.0.0.2"],
        preset={"web": {"http_proxy": "http://localhost:8080"}},
    )
    scan1 = await bbot_server.create_scan(scan1_obj)

    scans = await bbot_server.get_scans()
    assert len(scans) == 1
    assert scans[0].name == "scan1"
    assert scans[0].target == ["localhost"]
    assert scans[0].whitelist == ["127.0.0.1", "evilcorp.com"]
    assert scans[0].blacklist == ["127.0.0.2"]
    assert scans[0].preset == {"web": {"http_proxy": "http://localhost:8080"}}

    scan2_obj = Scan(
        name="scan2",
        target=["localhost"],
        whitelist=["127.0.0.1", "evilcorp.com"],
        blacklist=["127.0.0.2"],
        preset={"web": {"http_proxy": "http://localhost:8080"}},
    )
    scan2 = await bbot_server.create_scan(scan2_obj)

    scans = await bbot_server.get_scans()
    assert len(scans) == 2
    assert scans[1].name == "scan2"
    assert scans[1].target == ["localhost"]
    assert scans[1].whitelist == ["127.0.0.1", "evilcorp.com"]
    assert scans[1].blacklist == ["127.0.0.2"]
    assert scans[1].preset == {"web": {"http_proxy": "http://localhost:8080"}}

    # delete scan1
    await bbot_server.delete_scan(scan1.name)
    scans = await bbot_server.get_scans()
    assert len(scans) == 1
    assert scans[0].name == "scan2"

    # edit scan2
    scan2.name = "scan2_edited"
    scan2.preset = {"web": {"http_proxy": "http://localhost:8081"}}
    await bbot_server.edit_scan("scan2", scan2)
    scans = await bbot_server.get_scans()
    assert len(scans) == 1
    assert scans[0].name == "scan2_edited"
    assert scans[0].preset == {"web": {"http_proxy": "http://localhost:8081"}}
