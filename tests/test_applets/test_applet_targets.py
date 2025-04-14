import pytest
import asyncio
from contextlib import suppress

from tests.test_applets.base import BaseAppletTest
from bbot_server.errors import BBOTServerNotFoundError, BBOTServerValueError


# test CRUD operations on targets
async def test_applet_targets(bbot_server):
    bbot_server = await bbot_server()

    # watch for scope activity
    activities = []

    async def handle_activity():
        async for activity in bbot_server.tail_assets(n=10):
            activities.append(activity)

    activity_tail_task = asyncio.create_task(handle_activity())
    await asyncio.sleep(0.5)

    targets = await bbot_server.get_targets()
    assert targets == []

    num_targets = await bbot_server.target_count()
    assert num_targets == 0

    # create a target
    target1 = await bbot_server.create_target(
        name="target1",
        description="target1 description",
        target=["localhost"],
        whitelist=["127.0.0.1", "evilcorp.com"],
        blacklist=["127.0.0.2"],
    )

    assert target1.created is not None
    assert target1.modified is not None
    # Allow for small time differences (<10ms) between created and modified timestamps
    time_diff = abs(target1.created - target1.modified)
    assert time_diff < 0.01, f"Time difference between created and modified is {time_diff}s, expected <0.01s"

    num_targets = await bbot_server.target_count()
    assert num_targets == 1

    targets = await bbot_server.get_targets()
    assert len(targets) == 1
    target = targets[0]
    assert target.name == "target1"
    assert target.id == target1.id
    assert target.description == "target1 description"
    assert target.target == ["localhost"]
    assert target.whitelist == ["127.0.0.1", "evilcorp.com"]
    assert target.blacklist == ["127.0.0.2"]
    assert target.default is True

    target_ids = await bbot_server.get_target_ids()
    assert len(target_ids) == 1
    assert target_ids[0] == target1.id

    # create a second target
    target2 = await bbot_server.create_target(
        name="target2",
        description="target2 description",
        target=["localhost"],
        whitelist=["127.0.0.1", "evilcorp.com"],
        blacklist=["127.0.0.2"],
    )

    targets = await bbot_server.get_targets()
    assert len(targets) == 2
    target = targets[1]
    assert target.name == "target2"
    assert target.id == target2.id
    assert target.description == "target2 description"
    assert target.target == ["localhost"]
    assert target.whitelist == ["127.0.0.1", "evilcorp.com"]
    assert target.blacklist == ["127.0.0.2"]
    assert target.default is False

    target_ids = await bbot_server.get_target_ids(debounce=0.0)
    assert len(target_ids) == 2
    assert target1.id in target_ids
    assert target2.id in target_ids

    # delete target1
    await bbot_server.delete_target(target1.id)
    targets = await bbot_server.get_targets()
    assert len(targets) == 1
    target = targets[0]
    assert target.name == "target2"

    with pytest.raises(BBOTServerNotFoundError):
        await bbot_server.get_target(id=target1.id)

    # target2 should now be the default target
    target = await bbot_server.get_target()
    assert target.name == "target2"
    assert target.default is True

    # edit target2
    target2.name = "target2_edited"
    target2.target = []
    target2.whitelist = []
    target2.blacklist = []
    await asyncio.sleep(0.1)
    await bbot_server.update_target(target2.id, target2)
    targets = await bbot_server.get_targets()
    assert len(targets) == 1
    target = targets[0]
    assert target.name == "target2_edited"
    assert target.target == []
    assert target.whitelist == []
    assert target.blacklist == []
    assert abs(target.created - target.modified) >= 0.1, "Modified timestamp wasn't updated"

    # add target3
    target3 = await bbot_server.create_target(
        name="target3",
        description="target3 description",
        target=["localhost"],
        whitelist=["127.0.0.1", "evilcorp.com"],
        blacklist=["127.0.0.2"],
    )

    # set target3 as the default target
    await bbot_server.set_default_target(target3.id)
    target = await bbot_server.get_target()
    assert target.name == "target3"
    assert target.default is True

    # target2 should no longer be default
    target = await bbot_server.get_target(id=target2.id)
    assert target.name == "target2_edited"
    assert target.default is False

    # create target4
    await bbot_server.create_target(
        name="target4",
        description="target4 description",
        target=["localhost"],
        whitelist=["127.0.0.1", "evilcorp.com"],
        blacklist=["127.0.0.2"],
    )

    # deleting a target that's a part of a scan should not work
    scan = await bbot_server.create_scan(name="scan", target=target2.id)
    with pytest.raises(BBOTServerValueError):
        await bbot_server.delete_target(target2.id)

    # deleting the default target without specifying a new default target should raise an error
    with pytest.raises(BBOTServerValueError):
        await bbot_server.delete_target(target3.id)

    # deleting the default target with a new default target should work
    await bbot_server.delete_target(target3.id, new_default_target_id=target2.id)

    # delete the scan associated with target2
    await bbot_server.delete_scan(scan.id)

    # deleting target2 should work now, even though it's the default target
    # because there's only one other target left, it's assumed to be the new default
    await bbot_server.delete_target(target2.id)

    # since target4 is the only target left, it's now the default target
    targets = await bbot_server.get_targets()
    assert len(targets) == 1
    target = targets[0]
    assert target.name == "target4"
    assert target.default is True

    activity_types = [activity.type for activity in activities]
    assert activity_types == ["TARGET_CREATED", "TARGET_CREATED", "TARGET_UPDATED", "TARGET_CREATED", "TARGET_CREATED"]

    # cancel activity task
    activity_tail_task.cancel()
    with suppress(asyncio.CancelledError):
        await activity_tail_task


async def test_scope_checks(bbot_server):
    bbot_server = await bbot_server()

    # simple target
    await bbot_server.create_target(
        name="target1",
        description="target1 description",
        target=["evilcorp.com"],
    )

    targets = await bbot_server.get_targets()
    assert len(targets) == 1
    target = targets[0]
    assert target.name == "target1"
    assert target.target == ["evilcorp.com"]
    assert target.whitelist == None
    assert target.blacklist == None

    assert await bbot_server.in_scope("evilcorp.com") == True
    assert await bbot_server.in_scope("external.evilcorp.com") == True
    assert await bbot_server.in_scope("http://test.evilcorp.com") == True
    assert await bbot_server.in_scope("bob@evilcorp.com") == True
    assert await bbot_server.in_scope("test.evilcorp.net") == False
    assert await bbot_server.in_scope("http://test.evilcorp.net") == False

    # complex target
    target2 = await bbot_server.create_target(
        name="target2",
        description="target2 description",
        target=["evilcorp.org"],
        whitelist=["127.0.0.1/24", "external.evilcorp.org"],
        blacklist=["127.0.0.2", "test.external.evilcorp.org", "RE:plumbus"],
    )

    # default target is still target1
    assert await bbot_server.in_scope("evilcorp.org") == False

    # specifying target2 should return True
    assert await bbot_server.in_scope("evilcorp.org", target_id=target2.id) == False
    assert await bbot_server.in_scope("www.external.evilcorp.org", target_id=target2.id) == True
    assert await bbot_server.in_scope("plumbus.external.evilcorp.org", target_id=target2.id) == False
    assert await bbot_server.in_scope("http://www.external.evilcorp.org", target_id=target2.id) == True
    assert await bbot_server.in_scope("http://plumbus.external.evilcorp.org", target_id=target2.id) == False
    assert (
        await bbot_server.in_scope("http://www.external.evilcorp.org/plumbus/index.html", target_id=target2.id)
        == False
    )
    assert (
        await bbot_server.in_scope("http://www.external.evilcorp.org/index.html?plumbus=a", target_id=target2.id)
        == False
    )
    assert (
        await bbot_server.in_scope("http://www.external.evilcorp.org/index.html#plumbus", target_id=target2.id) == True
    )
    assert await bbot_server.in_scope("127.0.0.1", target_id=target2.id) == True
    assert await bbot_server.in_scope("127.0.0.2", target_id=target2.id) == False
    assert await bbot_server.in_scope("127.0.0.3", target_id=target2.id) == True
    assert await bbot_server.in_scope("www.test.external.evilcorp.org", target_id=target2.id) == False


class TestTargetScopeMaintenance(BaseAppletTest):
    needs_watchdog = True

    async def setup(self):
        assert await self.bbot_server.get_hosts() == []
        assert await self.bbot_server.get_targets() == []

        # target with domain blacklist
        self.target1 = await self.bbot_server.create_target(
            name="evilcorp",
            description="evilcorp target",
            whitelist=["evilcorp.com"],
            blacklist=["www.evilcorp.com"],
        )

        # target with IP blacklist
        self.target2 = await self.bbot_server.create_target(
            name="www evilcorp",
            description="www evilcorp target",
            whitelist=["www.evilcorp.com", "localhost.evilcorp.com", "127.0.0.1"],
            blacklist=["127.0.0.2"],
        )

    async def after_scan_1(self):
        assets = [a async for a in self.bbot_server.get_assets()]
        target_1_assets = {a.host for a in assets if self.target1.id in a.scope}
        target_2_assets = {a.host for a in assets if self.target2.id in a.scope}

        assert target_1_assets == {
            "evilcorp.com",
            "www2.evilcorp.com",
            "localhost.evilcorp.com",
            "cname.evilcorp.com",
            "api.evilcorp.com",
        }
        assert target_2_assets == {
            "www.evilcorp.com",
            "localhost.evilcorp.com",
            "127.0.0.1",
        }

    async def after_scan_2(self):
        assets = [a async for a in self.bbot_server.get_assets()]
        target_1_assets = {a.host for a in assets if self.target1.id in a.scope}
        target_2_assets = {a.host for a in assets if self.target2.id in a.scope}

        assert target_1_assets == {
            "evilcorp.com",
            "www2.evilcorp.com",
            "localhost.evilcorp.com",
            "cname.evilcorp.com",
            "api.evilcorp.com",
        }
        assert target_2_assets == {
            "www.evilcorp.com",
            # localhost.evilcorp.com is no longer in scope for target2 due to its IP changing
            "127.0.0.1",
        }

        # add a.com to target2
        self.target2.whitelist = ["127.0.0.0/24"]
        await self.bbot_server.update_target(self.target2.id, self.target2)
        await asyncio.sleep(0.1)

        assets = [a async for a in self.bbot_server.get_assets()]

        # a.com (127.0.0.3) and b.com (127.0.0.4) are now part of the target
        target_2_assets = {a.host for a in assets if self.target2.id in a.scope}
        assert target_2_assets == {"a.com", "b.com", "www.evilcorp.com", "127.0.0.1"}

    async def after_archive(self):
        pass
