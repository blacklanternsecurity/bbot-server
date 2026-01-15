import pytest
import asyncio
from contextlib import suppress

from tests.test_applets.base import BaseAppletTest
from bbot_server.modules.targets.targets_models import CreateTarget, Target
from bbot_server.errors import BBOTServerNotFoundError, BBOTServerValueError


# test CRUD operations on targets
async def test_applet_targets(bbot_server):
    bbot_server = await bbot_server()

    # watch for scope activity
    activities = []

    async def handle_activity():
        async for activity in bbot_server.tail_activities(n=10):
            activities.append(activity)

    activity_tail_task = asyncio.create_task(handle_activity())
    await asyncio.sleep(0.5)

    targets = await bbot_server.get_targets()
    assert targets == []

    num_targets = await bbot_server.target_count()
    assert num_targets == 0

    # create a target
    target1 = CreateTarget(
        name="target1",
        description="target1 description",
        target=["127.0.0.1", "evilcorp.com"],
        seeds=["localhost"],
        blacklist=["127.0.0.2"],
    )
    target1 = await bbot_server.create_target(target1)

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
    assert target.seeds == ["localhost"]
    assert target.target == ["127.0.0.1", "evilcorp.com"]
    assert target.blacklist == ["127.0.0.2"]
    assert target.default is True

    target_ids = await bbot_server.get_target_ids()
    assert len(target_ids) == 1
    assert target_ids[0] == target1.id

    # creating a target with the same name should raise an error
    with pytest.raises(BBOTServerValueError, match='Target with name "target1" already exists'):
        try:
            target = CreateTarget(
                name="target1",
                target=["localhost"],
            )
            target = await bbot_server.create_target(target)
        except BBOTServerValueError as e:
            assert e.detail["name"] == "target1"
            raise

    # we can create an identical target with allow_duplicate_hash=True (the default)
    duptarget1 = CreateTarget(
        name="duptarget1", target=["127.0.0.1", "evilcorp.com"], seeds=["localhost"], blacklist=["127.0.0.2"]
    )
    duptarget1 = await bbot_server.create_target(duptarget1)
    assert duptarget1.hash == target1.hash

    all_targets = await bbot_server.get_targets()
    assert len(all_targets) == 2
    assert duptarget1.id in [t.id for t in all_targets]
    assert target1.id in [t.id for t in all_targets]

    # creating a target with the same hash should raise an error with allow_duplicate_hash=False
    target3 = CreateTarget(
        name="target3", target=["127.0.0.1", "evilcorp.com"], seeds=["localhost"], blacklist=["127.0.0.2"]
    )
    with pytest.raises(BBOTServerValueError, match="Identical target already exists"):
        target3 = await bbot_server.create_target(target3, allow_duplicate_hash=False)
    all_targets = await bbot_server.get_targets()
    assert len(all_targets) == 2
    assert duptarget1.id in [t.id for t in all_targets]
    assert target1.id in [t.id for t in all_targets]

    await bbot_server.delete_target(duptarget1.id)

    # create a second target
    target2 = CreateTarget(
        name="target2",
        description="target2 description",
        seeds=["localhost"],
        target=["127.0.0.1", "evilcorp.com", "localhost2"],
        blacklist=["127.0.0.2"],
    )
    target2 = await bbot_server.create_target(target2)

    assert target2.target_hash != target1.target_hash
    assert target2.blacklist_hash == target1.blacklist_hash
    assert target2.seed_hash == target1.seed_hash
    assert target2.hash != target1.hash
    assert target2.scope_hash != target1.scope_hash

    targets = await bbot_server.get_targets()
    assert len(targets) == 2
    target = targets[1]
    assert target.name == "target2"
    assert target.id == target2.id
    assert target.description == "target2 description"
    assert target.seeds == ["localhost"]
    assert target.target == ["127.0.0.1", "evilcorp.com", "localhost2"]
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
    target2.seeds = []
    target2.target = []
    target2.blacklist = []
    await asyncio.sleep(0.1)
    await bbot_server.update_target(target2.id, target2)
    targets = await bbot_server.get_targets()
    assert len(targets) == 1
    target = targets[0]
    assert target.name == "target2_edited"
    assert target.seeds == []
    assert target.target == []
    assert target.blacklist == []
    assert abs(target.created - target.modified) >= 0.1, "Modified timestamp wasn't updated"

    # add target3
    target3 = CreateTarget(
        name="target3",
        description="target3 description",
        seeds=["localhost", "localhost3"],
        target=["127.0.0.1", "evilcorp.com", "localhost3"],
        blacklist=["127.0.0.2"],
    )
    target3 = await bbot_server.create_target(target3)

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
    target4 = CreateTarget(
        name="target4",
        description="target4 description",
        seeds=["localhost"],
        target=["127.0.0.1", "evilcorp.com", "localhost4"],
        blacklist=["127.0.0.2"],
    )
    target4 = await bbot_server.create_target(target4)

    # deleting the default target without specifying a new default target should raise an error
    with pytest.raises(
        BBOTServerValueError, match="Cannot delete the default target without specifying a new default target."
    ):
        await bbot_server.delete_target(target3.id)

    # deleting the default target with a new default target should work
    await bbot_server.delete_target(target3.id, new_default_target_id=target2.id)

    # deleting target2 should work, even though it's the default target
    # because there's only one other target left, it's assumed to be the new default
    await bbot_server.delete_target(target2.id)

    # since target4 is the only target left, it's now the default target
    targets = await bbot_server.get_targets()
    assert len(targets) == 1
    target = targets[0]
    assert target.name == "target4"
    assert target.default is True

    activity_types = [activity.type for activity in activities]
    assert activity_types == [
        "TARGET_CREATED",
        "TARGET_CREATED",
        "TARGET_CREATED",
        "TARGET_UPDATED",
        "TARGET_CREATED",
        "TARGET_CREATED",
    ]

    # cancel activity task
    activity_tail_task.cancel()
    with suppress(asyncio.CancelledError):
        await activity_tail_task


# test CRUD operations on targets
async def test_target_default_names(bbot_server):
    bbot_server = await bbot_server()

    target1 = CreateTarget()
    with pytest.raises(BBOTServerValueError, match="Must provide at least one seed or target entry"):
        await bbot_server.create_target(target1)

    target1 = CreateTarget(target=["evilcorp.com"])
    target1 = await bbot_server.create_target(target1)
    assert target1.name == "Target 1"
    target2 = CreateTarget(target=["evilcorp.org"])
    target2 = await bbot_server.create_target(target2)
    assert target2.name == "Target 2"
    target3 = CreateTarget(target=["evilcorp.net"])
    target3 = await bbot_server.create_target(target3)
    assert target3.name == "Target 3"


async def test_target_size(bbot_server):
    bbot_server = await bbot_server()

    target = CreateTarget(
        seeds=["evilcorp.com", "1.2.3.4/30"],
        target=["evilcorp.com", "1.2.3.4/29"],
        blacklist=["www.evilcorp.com", "test.evilcorp.com", "1.2.3.5/28"],
    )
    target = await bbot_server.create_target(target)
    assert target.seed_size == 5  # /30 (4 hosts) + 1 domain
    assert target.target_size == 9  # /29 (8 hosts) + 1 domain
    assert target.blacklist_size == 18  # /28 (16 hosts) + 2 domains


async def test_scope_checks(bbot_server):
    bbot_server = await bbot_server()

    # simple target
    target1 = CreateTarget(
        name="target1",
        description="target1 description",
        target=["evilcorp.com"],
    )
    await bbot_server.create_target(target1)

    targets = await bbot_server.get_targets()
    assert len(targets) == 1
    target = targets[0]
    assert target.name == "target1"
    assert target.target == ["evilcorp.com"]
    assert target.seeds == None
    assert target.blacklist == []

    assert await bbot_server.in_scope("evilcorp.com") == True
    assert await bbot_server.in_scope("external.evilcorp.com") == True
    assert await bbot_server.in_scope("http://test.evilcorp.com") == True
    assert await bbot_server.in_scope("bob@evilcorp.com") == True
    assert await bbot_server.in_scope("test.evilcorp.net") == False
    assert await bbot_server.in_scope("http://test.evilcorp.net") == False

    # complex target
    target2 = CreateTarget(
        name="target2",
        description="target2 description",
        seeds=["evilcorp.org"],
        target=["127.0.0.1/24", "external.evilcorp.org"],
        blacklist=["127.0.0.2", "test.external.evilcorp.org", "RE:plumbus"],
    )
    target2 = await bbot_server.create_target(target2)

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


async def test_target_copy(bbot_server):
    bbot_server = await bbot_server()
    target = CreateTarget(
        name="target",
        description="target description",
        target=["evilcorp.com"],
    )
    target = await bbot_server.create_target(target)
    target_copy = await bbot_server.copy_target(target.id)

    assert target_copy.name == "target Copy"
    assert target_copy.description == "target description"
    assert target_copy.target == ["evilcorp.com"]
    assert target_copy.seeds is None
    assert target_copy.blacklist == []
    assert target_copy.strict_dns_scope == False
    assert target_copy.id != target.id

    with pytest.raises(BBOTServerValueError, match='Target with name "target" already exists'):
        await bbot_server.copy_target(target.id, name="target")

    targets = await bbot_server.get_targets()
    assert set([t.id for t in targets]) == {target.id, target_copy.id}
    assert set([t.name for t in targets]) == {"target", "target Copy"}


# tests to make sure there is only ever one default target
async def test_target_default_uniqueness(bbot_server):
    bbot_server = await bbot_server()

    target1 = CreateTarget(
        name="target1",
        description="target1 description",
        target=["evilcorp.com"],
    )
    target1 = await bbot_server.create_target(target1)
    target1 = await bbot_server.get_target(id=target1.id)
    # the first target should be the default target
    assert target1.default is True
    target2 = CreateTarget(
        name="target2",
        description="target2 description",
        target=["evilcorp.com"],
        default=True,
    )
    target2 = await bbot_server.create_target(target2)
    target2 = await bbot_server.get_target(id=target2.id)
    # when a new target is created with default=True, it should replace the default target
    assert target2.default is True
    target1 = await bbot_server.get_target(id=target1.id)
    assert target1.default is False

    target1_updated = Target(
        name="target1",
        description="target1 description",
        target=["evilcorp.com"],
        default=True,
    )
    # updating target1 back to default=true should set target2.default to false
    await bbot_server.update_target(target1.id, target1_updated)
    try:
        target1 = await bbot_server.get_target(id=target1.id)
    except Exception as e:
        all_targets = await bbot_server.get_targets()
        raise Exception(f"Error getting target with id {target1.id}: {e}, all targets: {all_targets}") from e

    assert target1.default is True
    target2 = await bbot_server.get_target(id=target2.id)
    assert target2.default is False


class TestTargetScopeMaintenance(BaseAppletTest):
    needs_watchdog = True

    async def setup(self):
        assert await self.bbot_server.get_hosts() == []
        assert await self.bbot_server.get_targets() == []

        # target with domain blacklist
        target1 = CreateTarget(
            name="evilcorp",
            description="evilcorp target",
            seeds=["evilcorp.com"],
            target=["evilcorp.com"],
            blacklist=["www.evilcorp.com"],
        )
        self.target1 = await self.bbot_server.create_target(target1)
        # target with IP blacklist
        target2 = CreateTarget(
            name="www evilcorp",
            description="www evilcorp target",
            seeds=["evilcorp.com"],
            target=["www.evilcorp.com", "localhost.evilcorp.com", "127.0.0.1"],
            blacklist=["127.0.0.2"],
        )
        self.target2 = await self.bbot_server.create_target(target2)

    async def after_scan_1(self):
        assets = [a async for a in self.bbot_server.list_assets()]
        target_1_assets = {a.host for a in assets if self.target1.id in a.scope}
        target_2_assets = {a.host for a in assets if self.target2.id in a.scope}

        assert target_1_assets == {
            "evilcorp.com",
            "www2.evilcorp.com",
            "localhost.evilcorp.com",
            "cname.evilcorp.com",
            "t1.tech.evilcorp.com",
            "t2.tech.evilcorp.com",
            "api.evilcorp.com",
        }
        assert target_2_assets == {
            "www.evilcorp.com",
            "localhost.evilcorp.com",
            "127.0.0.1",
        }

    async def after_scan_2(self):
        assets = [a async for a in self.bbot_server.list_assets()]
        target_1_assets = {a.host for a in assets if self.target1.id in a.scope}
        target_2_assets = {a.host for a in assets if self.target2.id in a.scope}

        assert target_1_assets == {
            "evilcorp.com",
            "www2.evilcorp.com",
            "localhost.evilcorp.com",
            "cname.evilcorp.com",
            "t1.tech.evilcorp.com",
            "t2.tech.evilcorp.com",
            "api.evilcorp.com",
        }
        assert target_2_assets == {
            "www.evilcorp.com",
            # localhost.evilcorp.com is no longer in scope for target2 due to its IP changing
            "127.0.0.1",
        }

        target_1_assets_filtered = {a.host async for a in self.bbot_server.list_assets(target_id="evilcorp")}
        assert target_1_assets_filtered == target_1_assets
        target_2_assets_filtered = {a.host async for a in self.bbot_server.list_assets(target_id="www evilcorp")}
        assert target_2_assets_filtered == target_2_assets
        target_assets_default = {a.host async for a in self.bbot_server.list_assets(target_id="DEFAULT")}
        assert target_assets_default == target_1_assets

        # add evilcorp.azure.com to target2
        self.target2.target = ["127.0.0.0/24"]
        await self.bbot_server.update_target(self.target2.id, self.target2)
        await asyncio.sleep(1.0)

        assets = [a async for a in self.bbot_server.list_assets()]

        # evilcorp.azure.com (127.0.0.3) and b.com (127.0.0.4) are now part of the target
        target_2_assets = {a.host for a in assets if self.target2.id in a.scope}
        assert target_2_assets == {"evilcorp.azure.com", "evilcorp.amazonaws.com", "www.evilcorp.com", "127.0.0.1"}

    async def after_archive(self):
        pass
