import asyncio

from tests.test_applets.base import BaseAppletTest


class TestAppletAssets(BaseAppletTest):
    needs_watchdog = True

    async def setup(self):
        # # make sure all asset fields have annotations
        # for field, field_info in self.bbot_server.assets.model.model_fields.items():
        #     if field_info.annotation is None:
        #         raise ValueError(f"Field '{field}' has no type annotation")
        #     if field_info.default_factory is None:
        #         raise ValueError(f"Field '{field}' has no default factory")

        assert await self.bbot_server.get_hosts() == []

    async def after_scan_1(self):
        assert set(await self.bbot_server.get_hosts()) == {
            "1.2.3.4",
            "127.0.0.1",
            "192.168.1.1",
            "192.168.1.2",
            "5.6.7.8",
            "evilcorp.azure.com",
            "api.evilcorp.com",
            "cname.evilcorp.com",
            "evilcorp.com",
            "localhost.evilcorp.com",
            "www.evilcorp.com",
            "www2.evilcorp.com",
            "tech1.evilcorp.com",
            "tech2.evilcorp.com",
            "testevilcorp.com",
        }

    async def after_scan_2(self):
        assert set(await self.bbot_server.get_hosts()) == {
            "1.2.3.4",
            "127.0.0.1",
            "127.0.0.2",
            "192.168.1.1",
            "192.168.1.2",
            "5.6.7.8",
            "evilcorp.azure.com",
            "api.evilcorp.com",
            "evilcorp.amazonaws.com",
            "cname.evilcorp.com",
            "evilcorp.com",
            "localhost.evilcorp.com",
            "www.evilcorp.com",
            "www2.evilcorp.com",
            "tech1.evilcorp.com",
            "tech2.evilcorp.com",
            "testevilcorp.com",
        }

    async def after_archive(self):
        assert set(await self.bbot_server.get_hosts()) == {
            "1.2.3.4",
            "127.0.0.1",
            "127.0.0.2",
            "192.168.1.1",
            "192.168.1.2",
            "5.6.7.8",
            "evilcorp.azure.com",
            "api.evilcorp.com",
            "evilcorp.amazonaws.com",
            "cname.evilcorp.com",
            "evilcorp.com",
            "localhost.evilcorp.com",
            "www.evilcorp.com",
            "www2.evilcorp.com",
            "tech1.evilcorp.com",
            "tech2.evilcorp.com",
            "testevilcorp.com",
        }

        assert set(await self.bbot_server.get_hosts(domain="evilcorp.com")) == {
            "evilcorp.com",
            "api.evilcorp.com",
            "cname.evilcorp.com",
            "www.evilcorp.com",
            "www2.evilcorp.com",
            "localhost.evilcorp.com",
            "tech1.evilcorp.com",
            "tech2.evilcorp.com",
        }


# test to make sure you can filter assets by target
async def test_applet_target_filter(bbot_server, bbot_events):
    bbot_server = await bbot_server(needs_watchdog=True)

    target1 = await bbot_server.create_target(
        whitelist=["evilcorp.com", "127.0.0.0/30"],
        blacklist=["localhost.evilcorp.com"],
    )

    # ingest BBOT events
    scan1_events, scan2_events = bbot_events
    for e in scan1_events:
        await bbot_server.insert_event(e)

    # wait for events to be processed
    await asyncio.sleep(1)

    all_hosts = {
        "evilcorp.com",
        "1.2.3.4",
        "5.6.7.8",
        "192.168.1.1",
        "192.168.1.2",
        "www2.evilcorp.com",
        "api.evilcorp.com",
        "localhost.evilcorp.com",
        "cname.evilcorp.com",
        "www.evilcorp.com",
        "127.0.0.1",
        "evilcorp.azure.com",
        "testevilcorp.com",
        "tech1.evilcorp.com",
        "tech2.evilcorp.com",
    }

    all_hosts_target1 = {
        "127.0.0.1",
        "evilcorp.com",
        "www2.evilcorp.com",
        "api.evilcorp.com",
        "cname.evilcorp.com",
        "www.evilcorp.com",
        "evilcorp.azure.com",  # this one resolves to 127.0.0.3 so it matches
        "tech1.evilcorp.com",
        "tech2.evilcorp.com",
    }

    all_hosts_target2 = {
        "1.2.3.4",
        "evilcorp.com",
        "www.evilcorp.com",
        "api.evilcorp.com",
    }

    # get assets (without target filter)
    assets = [a.host async for a in bbot_server.get_assets()]
    assert set(assets) == all_hosts
    hosts = await bbot_server.get_hosts()
    assert set(hosts) == all_hosts

    # get assets (with default target filter)
    assets = [a.host async for a in bbot_server.get_assets(target_id="DEFAULT")]
    assert set(assets) == all_hosts_target1
    hosts = await bbot_server.get_hosts(target_id="DEFAULT")
    assert set(hosts) == all_hosts_target1

    # get assets (with target filter)
    assets = [a.host async for a in bbot_server.get_assets(target_id=target1.id)]
    assert set(assets) == all_hosts_target1
    hosts = await bbot_server.get_hosts(target_id=target1.id)
    assert set(hosts) == all_hosts_target1

    # new target
    target = await bbot_server.create_target(
        whitelist=["1.2.3.0/24"],
        blacklist=["www2.evilcorp.com"],
    )

    # wait for events to be tagged with new target
    await asyncio.sleep(1)

    # get assets (with new target filter)
    assets = [a.host async for a in bbot_server.get_assets(target_id=target.id)]
    assert set(assets) == all_hosts_target2
    hosts = await bbot_server.get_hosts(target_id=target.id)
    assert set(hosts) == all_hosts_target2
