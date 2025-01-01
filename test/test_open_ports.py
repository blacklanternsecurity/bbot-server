import pytest

from bbot import Scanner
from bbot.models.pydantic import Event


@pytest.mark.asyncio
async def test_open_ports(bbot_server):
    scan = Scanner()
    host_event = scan.make_event("www.evilcorp.com", "DNS_NAME", parent=scan.root_event)
    port_80_event = scan.make_event("www.evilcorp.com:80", "OPEN_TCP_PORT", parent=host_event)
    port_443_event = scan.make_event("www.evilcorp.com:443", "OPEN_TCP_PORT", parent=host_event)
    host_event_pydantic = Event(**host_event.json())
    port_80_event_pydantic = Event(**port_80_event.json())
    port_443_event_pydantic = Event(**port_443_event.json())

    print(bbot_server)

    # make sure the asset database is empty
    assets = await bbot_server.get_assets()
    assert assets == []

    # insert the host event
    try:
        activities = await bbot_server.events.insert_event(host_event_pydantic)
        assert len(activities) == 1
        assert activities[0].type == "NEW_ASSET"
    except BaseException as e:
        print("ERRORALJSDGHLASDKFsadf", e)
        import traceback

        traceback.print_exc()
        return

    # make sure the asset took
    assets = await bbot_server.get_assets()
    assert len(assets) == 1
    assert assets[0].host == host_event_pydantic.host
    assert not assets[0].extra_fields

    # insert the port 80 event
    activities = await bbot_server.events.insert_event(port_80_event_pydantic)
    assert len(activities) == 1
    assert activities[0].type == "PORT_OPENED"

    # make sure the open port is now listed
    assets = await bbot_server.get_assets()
    assert len(assets) == 1
    assert assets[0].host == host_event_pydantic.host
    assert assets[0].extra_fields["open_ports"] == [80]

    # insert the port 443 event
    activities = await bbot_server.events.insert_event(port_443_event_pydantic)
    assert len(activities) == 1
    assert activities[0].type == "PORT_OPENED"

    # make sure the open port is now listed
    assets = await bbot_server.get_assets()
    assert len(assets) == 1
    assert assets[0].host == host_event_pydantic.host
    assert assets[0].extra_fields["open_ports"] == [80, 443]
