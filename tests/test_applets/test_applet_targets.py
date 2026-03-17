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

    num_targets = await bbot_server.count_targets()
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

    num_targets = await bbot_server.count_targets()
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
    duptarget1 = await bbot_server.create_target(
        name="duptarget1", target=["127.0.0.1", "evilcorp.com"], seeds=["localhost"], blacklist=["127.0.0.2"]
    )
    assert duptarget1.hash == target1.hash

    all_targets = await bbot_server.get_targets()
    assert len(all_targets) == 2
    assert duptarget1.id in [t.id for t in all_targets]
    assert target1.id in [t.id for t in all_targets]

    # creating a target with the same hash should raise an error with allow_duplicate_hash=False
    with pytest.raises(BBOTServerValueError, match="Identical target already exists"):
        await bbot_server.create_target(
            name="target3",
            target=["127.0.0.1", "evilcorp.com"],
            seeds=["localhost"],
            blacklist=["127.0.0.2"],
            allow_duplicate_hash=False,
        )
    all_targets = await bbot_server.get_targets()
    assert len(all_targets) == 2
    assert duptarget1.id in [t.id for t in all_targets]
    assert target1.id in [t.id for t in all_targets]

    await bbot_server.delete_target(duptarget1.id)

    # create a second target
    target2 = await bbot_server.create_target(
        name="target2",
        description="target2 description",
        seeds=["localhost"],
        target=["127.0.0.1", "evilcorp.com", "localhost2"],
        blacklist=["127.0.0.2"],
    )

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
    target3 = await bbot_server.create_target(
        name="target3",
        description="target3 description",
        seeds=["localhost", "localhost3"],
        target=["127.0.0.1", "evilcorp.com", "localhost3"],
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
        seeds=["localhost"],
        target=["127.0.0.1", "evilcorp.com", "localhost4"],
        blacklist=["127.0.0.2"],
    )

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

    with pytest.raises(BBOTServerValueError, match="Must provide at least one seed or target entry"):
        await bbot_server.create_target()

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

    target = await bbot_server.create_target(
        seeds=["evilcorp.com", "1.2.3.4/30"],
        target=["evilcorp.com", "1.2.3.4/29"],
        blacklist=["www.evilcorp.com", "test.evilcorp.com", "1.2.3.5/28"],
    )
    assert target.seed_size == 5  # /30 (4 hosts) + 1 domain
    assert target.target_size == 9  # /29 (8 hosts) + 1 domain
    assert target.blacklist_size == 18  # /28 (16 hosts) + 2 domains


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
    assert target.seeds == None
    assert target.blacklist == []

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
        seeds=["evilcorp.org"],
        target=["127.0.0.1/24", "external.evilcorp.org"],
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


async def test_target_copy(bbot_server):
    bbot_server = await bbot_server()
    target = await bbot_server.create_target(
        name="target",
        description="target description",
        target=["evilcorp.com"],
    )
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

    target1 = await bbot_server.create_target(
        name="target1",
        description="target1 description",
        target=["evilcorp.com"],
    )
    target1 = await bbot_server.get_target(id=target1.id)
    # the first target should be the default target
    assert target1.default is True
    target2 = await bbot_server.create_target(
        name="target2",
        description="target2 description",
        target=["evilcorp.com"],
        default=True,
    )
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
    needs_worker = True

    async def setup(self):
        assert await self.bbot_server.get_hosts() == []
        assert await self.bbot_server.get_targets() == []

        # target with domain blacklist
        self.target1 = await self.bbot_server.create_target(
            name="evilcorp",
            description="evilcorp target",
            seeds=["evilcorp.com"],
            target=["evilcorp.com"],
            blacklist=["www.evilcorp.com"],
        )
        # target with IP blacklist
        self.target2 = await self.bbot_server.create_target(
            name="www evilcorp",
            description="www evilcorp target",
            seeds=["evilcorp.com"],
            target=["www.evilcorp.com", "localhost.evilcorp.com", "127.0.0.1"],
            blacklist=["127.0.0.2"],
        )

        # test query_targets with field selection and pagination
        all_targets = [t async for t in self.bbot_server.query_targets()]
        assert len(all_targets) == 2
        assert {t["name"] for t in all_targets} == {"evilcorp", "www evilcorp"}

        # field selection
        partial = [t async for t in self.bbot_server.query_targets(fields=["name", "id"])]
        assert len(partial) == 2
        for t in partial:
            assert set(t) == {"name", "id", "_id"}

        # pagination
        assert [t["name"] async for t in self.bbot_server.query_targets(limit=1)] == ["evilcorp"]
        assert [t["name"] async for t in self.bbot_server.query_targets(skip=1)] == ["www evilcorp"]
        assert [t["name"] async for t in self.bbot_server.query_targets(limit=1, skip=1)] == ["www evilcorp"]
        assert [t["name"] async for t in self.bbot_server.query_targets(skip=2)] == []

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

        # evilcorp.azure.com (127.0.0.3) and evilcorp.amazonaws.com (127.0.0.4) are now part of the target
        # 127.0.0.1 no longer exists (it is nowhere to be found in scan 2)
        # localhost.evilcorp.com (127.0.0.2) is still blacklisted
        target_2_assets = {a.host for a in assets if self.target2.id in a.scope}
        assert target_2_assets == {"evilcorp.azure.com", "evilcorp.amazonaws.com"}

    async def after_archive(self):
        pass


class TestTargetAddDomainPreservesExistingScope(BaseAppletTest):
    """
    Regression test for bug where adding a domain to an existing target
    caused all previously-in-scope assets to lose their scope, leaving only
    the newly added domain in scope.

    Root cause: refresh_asset_scope treated a None return from _check_scope
    (meaning "no change") as "out of scope", incorrectly removing the target
    from assets that were already in scope.
    """

    needs_worker = True

    async def setup(self):
        assert await self.bbot_server.get_hosts() == []
        assert await self.bbot_server.get_targets() == []

        # create a target with just evilcorp.com
        self.target = await self.bbot_server.create_target(
            name="evilcorp",
            description="evilcorp target",
            target=["evilcorp.com"],
        )

    async def after_scan_1(self):
        # verify evilcorp.com assets are in scope
        assets = [a async for a in self.bbot_server.list_assets()]
        target_assets = {a.host for a in assets if self.target.id in a.scope}
        assert "evilcorp.com" in target_assets
        assert len(target_assets) > 1, f"Expected multiple evilcorp.com assets in scope, got: {target_assets}"
        self.original_target_assets = target_assets

        # BUG REPRODUCTION: add a new domain to the target while keeping the existing one
        self.target.target = ["evilcorp.com", "testevilcorp.com"]
        await self.bbot_server.update_target(self.target.id, self.target)
        await asyncio.sleep(1.0)

        # verify that existing evilcorp.com assets are STILL in scope
        assets = [a async for a in self.bbot_server.list_assets()]
        target_assets_after = {a.host for a in assets if self.target.id in a.scope}

        # the new domain should also be in scope
        assert "testevilcorp.com" in target_assets_after, (
            f"Newly added domain testevilcorp.com should be in scope, got: {target_assets_after}"
        )

        # all previously in-scope assets should still be in scope
        missing = self.original_target_assets - target_assets_after
        assert not missing, (
            f"BUG: These assets lost their scope after adding a domain to the target: {missing}. "
            f"Before: {self.original_target_assets}, After: {target_assets_after}"
        )


class TestTargetUpdateRemovesTargetFromAssets(BaseAppletTest):
    """
    Regression test for bug where editing or deleting a target to remove a domain
    did not update assets to remove that target from their scope.

    https://github.com/blacklanternsecurity/bbot-server/issues/113

    Also tests that deleting a target doesn't break count_assets(target_id="DEFAULT") afterward
    """

    needs_worker = True

    async def setup(self):
        assert await self.bbot_server.get_hosts() == []
        assert await self.bbot_server.get_targets() == []

    async def after_scan_1(self):
        # count assets
        self.original_asset_count = await self.bbot_server.count_assets(target_id="DEFAULT")
        self.all_asset_count = await self.bbot_server.count_assets()
        # without any targets, "DEFAULT" target should return all assets
        assert self.original_asset_count > 0 and self.original_asset_count == self.all_asset_count

        # Create a target with evilcorp.com
        self.target = await self.bbot_server.create_target(
            name="bugtest",
            description="test target for bug reproduction",
            target=["evilcorp.com"],
        )

        # wait for new target to be processed
        await asyncio.sleep(1.0)

        # count assets again
        self.new_asset_count = await self.bbot_server.count_assets(target_id="DEFAULT")
        # our new count should be more than zero but less than the original count, since not all assets are in the target
        assert self.new_asset_count > 0
        assert self.new_asset_count < self.original_asset_count

        # Verify assets are in scope for our target
        assets = [a async for a in self.bbot_server.list_assets()]
        target_assets = {a.host for a in assets if self.target.id in a.scope}
        # Should have at least some evilcorp.com assets in scope
        assert len(target_assets) > 0, "Expected assets to be in scope for target"
        evilcorp_hosts = {h for h in target_assets if h.endswith("evilcorp.com")}
        assert len(evilcorp_hosts) > 0, f"Expected evilcorp.com hosts in target scope, got: {target_assets}"

        # BUG REPRODUCTION: Update the target to remove evilcorp.com
        # Replace with a totally different domain
        self.target.target = ["somethingelse.net"]
        await self.bbot_server.update_target(self.target.id, self.target)

        # Give worker time to process the TARGET_UPDATED activity
        await asyncio.sleep(1.0)

        # Check that assets no longer have this target in their scope
        assets = [a async for a in self.bbot_server.list_assets(target_id="DEFAULT")]
        target_assets = {a.host for a in assets if self.target.id in a.scope}
        assert len(target_assets) == 0, f"Expected no assets to be in scope for target, got: {target_assets}"

        # count assets again
        asset_count = await self.bbot_server.count_assets(target_id="DEFAULT")
        assert asset_count == 0, f"Expected asset count to be zero after target update, got: {asset_count}"

        # BUG: This assertion will fail because assets still have the old target in their scope
        evilcorp_hosts = {h for h in target_assets if h.endswith("evilcorp.com")}
        assert len(evilcorp_hosts) == 0, (
            f"BUG: evilcorp.com hosts should no longer be in target scope after target update, but found: {evilcorp_hosts}"
        )

        # delete the target
        await self.bbot_server.delete_target(self.target.id)

        # count assets again
        asset_count = await self.bbot_server.count_assets(target_id="DEFAULT")
        assert asset_count == self.original_asset_count == self.all_asset_count, (
            f"Expected asset count to be the same as before the target update, got: {asset_count}"
        )
