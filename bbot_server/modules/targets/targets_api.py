from uuid import UUID
from typing import Any
from contextlib import asynccontextmanager
from pymongo.errors import DuplicateKeyError
from bbot.scanner.target import BBOTTarget

from bbot_server.utils.misc import utc_now
from bbot_server.assets import Asset
from bbot_server.applets.base import BaseApplet, api_endpoint
from bbot_server.modules.activity.activity_models import Activity
from bbot_server.modules.targets.targets_models import Target, CreateTarget


class BlacklistedError(Exception):
    pass


# TODO:
# we already have hashing implemented for targets.
# we should include the target hash alongside its ID on assets,
# this way we know whether the scope is up to date
# we should have a single task for doing this, and automatically cancel or restart it if a new operation comes along
# this enables extremely fast and precise updates whenever a target is updated


class TargetsApplet(BaseApplet):
    name = "Targets"
    description = "scan targets"
    watched_events = ["*"]
    watched_activities = ["TARGET_CREATED", "TARGET_UPDATED"]
    attach_to = "scans"
    model = Target

    async def setup(self):
        # this holds the BBOTTarget instance for each target
        # enables near-instantaneous scope checks for any hosts
        self._scope_cache = {}
        # this holds an up-to-date list of all the target IDs
        self._target_ids = set()
        self._target_ids_modified = None
        return True, ""

    async def handle_event(self, event, asset):
        """
        Whenever a new event comes in, we check its host and all its A/AAAA records against our targets,
        and update its associated asset scope with the matching targets
        """
        activities = []

        if asset is None or event.host is None:
            return

        dns_children = getattr(event, "dns_children", {})

        # check event against each of our targets
        for target_id in await self.get_target_ids():
            bbot_target = await self._get_bbot_target(target_id)
            scope_result = await self._check_scope(event.host, dns_children, bbot_target, target_id, asset.scope)
            if scope_result is not None:
                scope_result.set_event(event)
                if scope_result.type == "NEW_IN_SCOPE_ASSET":
                    asset.scope = sorted(set(asset.scope) | set([target_id]))
                else:
                    asset.scope = sorted(set(asset.scope) - set([target_id]))
                activities.append(scope_result)
        return activities

    async def handle_activity(self, activity, asset: Asset = None):
        """
        Whenever an asset gets created/updated, we evaluate it against the current targets and tag it accordingly

        This lets us easily categorize+query assets by scope

        Similarly, whenever a target is created/updated/deleted, we iterate through all the assets and update them
        """
        # when a target is created or modified, we run a scope refresh on all the assets
        # debounce is set to 0.0 here because it's critical we're using the latest version of the target
        # if activity.type in ("TARGET_CREATED", "TARGET_UPDATED"):
        self.log.debug(f"Target created or updated. Refreshing asset scope")
        target_ids = await self.get_target_ids(debounce=0.0)
        for target_id in target_ids:
            target = await self._get_bbot_target(target_id, debounce=0.0)
            for host in await self.root.get_hosts():
                await self.refresh_asset_scope(host, target, target_id, emit_activity=True)

        # otherwise, for individual assets, we just refresh the scope for the given host
        # elif activity.host:
        #     asset_scope = await self.get_asset_scope(activity.host)
        #     await self.root._update_asset(activity.host, {"scope": [str(target_id) for target_id in asset_scope]})

        return []

    async def refresh_asset_scope(self, host: str, target: BBOTTarget, target_id: UUID, emit_activity: bool = False):
        """
        Given a host, evaluate it against all the current targets and tag it with each matching target's ID

        Args:
            host: the host to refresh the scope for
            target: the target to check against (BBOTTarget instance, this is passed in for performance reasons)
            target_id: the target ID
            emit_activity: whether to emit an activity when a change is detected in the asset's scope
        """
        self.log.debug(f"Refreshing asset scope for host {host}")
        asset = await self.root._get_asset(host=host, fields=["scope", "dns_links"])
        if asset is None:
            raise self.BBOTServerNotFoundError(f"Asset not found for host {host}")
        asset_scope = [UUID(_target_id) for _target_id in asset.get("scope", [])]
        asset_dns_links = asset.get("dns_links", {})
        scope_result = await self._check_scope(host, asset_dns_links, target, target_id, asset_scope)
        if scope_result is not None:
            if scope_result.type == "NEW_IN_SCOPE_ASSET":
                asset_scope = sorted(set(asset_scope) | set([target_id]))
            else:
                asset_scope = sorted(set(asset_scope) - set([target_id]))
            asset_results = await self.root.assets.collection.update_many(
                {"host": host},
                {"$set": {"scope": [str(_target_id) for _target_id in asset_scope]}},
            )
            self.log.debug(f"Updated {asset_results.modified_count} assets for host {host}")
            if emit_activity:
                await self.emit_activity(scope_result)

    async def get_asset_scope(self, host: str):
        """
        Given a host, get all the targets it's a part of

        This works by getting the asset and all its DNS links, then checking each one against all the targets
        """
        asset = await self.root.assets.collection.find_one({"host": host}, {"dns_links": 1}) or {}
        asset_dns_links = asset.get("dns_links", {})
        asset_scope = []
        for target_id in await self.get_target_ids():
            target = await self._get_bbot_target(target_id)
            in_scope = await self._check_scope(host, asset_dns_links, target, target_id)
            if in_scope:
                asset_scope.append(target_id)
        return sorted(asset_scope)

    @api_endpoint("/", methods=["GET"], summary="Get a single scan target by its name, id, or hash")
    async def get_target(self, id: str = None, hash: str = None) -> Target:
        """
        'id' can be either a target's ID (UUID) or its name.
        """
        target = await self._get_target(id=id, hash=hash)
        return Target(**target)

    @api_endpoint("/count", methods=["GET"], summary="Get the number of scan targets")
    async def target_count(self) -> int:
        return await self.collection.count_documents({})

    @api_endpoint("/set_default/{id}", methods=["POST"], summary="Set a target as the default target")
    async def set_default_target(self, id: str):
        """
        'id' can be either a target's ID (UUID) or its name.
        """
        # get target
        target = await self._get_target(id=id, fields=["id"])
        target_id = target["id"]
        await self.collection.update_one({"id": target_id}, {"$set": {"default": True}})
        # finally, set default=false on all other targets
        await self.collection.update_many({"id": {"$ne": target_id}}, {"$set": {"default": False}})

    @api_endpoint("/create", methods=["POST"], summary="Create a new scan target")
    async def create_target(
        self,
        target: CreateTarget,
        allow_duplicate_hash: bool = True,
    ) -> Target:
        print(f"Creating target: {target}")
        if not target.target and not target.seeds:
            raise self.BBOTServerValueError("Must provide at least one seed or target entry")
        if not target.name:
            target.name = await self.get_available_target_name()
        target = Target(
            name=target.name,
            description=target.description,
            seeds=target.seeds,
            target=target.target,
            blacklist=target.blacklist,
            strict_dns_scope=target.strict_dns_scope,
            default=target.default,
        )
        if await self.target_count() == 0:
            target.default = True
        async with self._handle_duplicate_target(target, allow_duplicate_hash):
            await self.collection.insert_one(target.model_dump())
        # if target is the default target, set all others to not be default
        if target.default:
            await self.collection.update_many({"id": {"$ne": str(target.id)}}, {"$set": {"default": False}})
        # emit an activity to show the target was created
        await self.emit_activity(
            type="TARGET_CREATED",
            detail={"target_id": str(target.id), "hash": target.hash, "scope_hash": target.scope_hash},
            description=f"Target [COLOR]{target.name}[/COLOR] created",
        )
        # update caches
        self._cache_put(target)
        self._target_ids.add(str(target.id))
        self._target_ids_modified = None
        return target

    @api_endpoint("/{id}", methods=["PATCH"], summary="Update a scan target by its id")
    async def update_target(
        self,
        id: UUID,
        target: Target,
        allow_duplicate_hash: bool = True,
    ) -> Target:
        target.id = id
        target.modified = utc_now()
        async with self._handle_duplicate_target(target, allow_duplicate_hash):
            await self.collection.update_one({"id": str(id)}, {"$set": target.model_dump()})
        if target.default:
            await self.collection.update_many({"id": {"$ne": str(target.id)}}, {"$set": {"default": False}})
        # emit an activity to show the target was updated
        await self.emit_activity(
            type="TARGET_UPDATED",
            detail={"target_id": str(target.id)},
            description=f"Target [COLOR]{target.name}[/COLOR] updated",
        )
        # reset target
        self._cache_put(target)
        return target

    @api_endpoint("/", methods=["DELETE"], summary="Delete a scan target by its id")
    async def delete_target(self, id: str = None, new_default_target_id: str = None) -> None:
        target = await self._get_target(id=id, fields=["id", "default"])
        target_id = str(target["id"])
        target_is_default = target["default"]

        # when we're deleting the default target, we need to set a new one
        if target_is_default:
            if new_default_target_id is None:
                num_targets = await self.target_count()
                # if there are 2 or less targets, we can assume the new default target
                if num_targets == 2:
                    # find the only other target that's not the one we're deleting
                    new_default_target = await self.collection.find_one({"default": False}, {"id": 1})
                    new_default_target_id = new_default_target["id"]
                # otherwise you're out of luck, you need to specify one
                elif num_targets > 2:
                    raise self.BBOTServerValueError(
                        "Cannot delete the default target without specifying a new default target."
                    )

        # delete the target
        await self.collection.delete_one({"id": target_id})

        # set the new default target
        if new_default_target_id is not None:
            await self.set_default_target(new_default_target_id)

        # clear scope cache
        if self._scope_cache is not None:
            self._scope_cache.pop(target_id, None)

        # forget the target ID forever
        self._target_ids.discard(target_id)

        # after deleting the target, also delete it from all the assets
        await self.root.assets.collection.update_many(
            {"scope": target_id},  # Find documents that have this target ID in their scope
            {"$pull": {"scope": target_id}},  # Remove this target ID from the scope array
        )

    @api_endpoint("/in_scope", methods=["GET"], summary="Check if a host or URL is in scope")
    async def in_scope(self, host: str, target_id: UUID = None) -> bool:
        bbot_target = await self._get_bbot_target(target_id)
        return bbot_target.in_scope(host)

    @api_endpoint("/in-target", methods=["GET"], summary="Check if a host or URL is in the target")
    async def is_in_target(self, host: str, target_id: UUID = None) -> bool:
        bbot_target = await self._get_bbot_target(target_id)
        return bbot_target.in_target(host)

    @api_endpoint("/blacklisted", methods=["GET"], summary="Check if a host or URL is blacklisted")
    async def is_blacklisted(self, host: str, target_id: UUID = None) -> bool:
        bbot_target = await self._get_bbot_target(target_id)
        return bbot_target.blacklisted(host)

    @api_endpoint("/list", methods=["GET"], summary="List targets")
    async def get_targets(self) -> list[Target]:
        cursor = self.collection.find()
        targets = await cursor.to_list(length=None)
        targets = [Target(**target) for target in targets]
        return targets

    @api_endpoint("/list_ids", methods=["GET"], summary="List all target IDs")
    async def get_target_ids(self, debounce: float = 5.0) -> list[UUID]:
        if self._target_ids_modified is None or utc_now() - self._target_ids_modified > debounce:
            self._target_ids = set(await self.collection.distinct("id"))
            self._target_ids_modified = utc_now()
        return [UUID(target_id) for target_id in self._target_ids]

    async def get_available_target_name(self) -> str:
        """
        Returns a target name that's guaranteed to not be in use, such as "Target 1", "Target 2", etc.
        """
        # Get all existing target names
        existing_names = await self.collection.distinct("name")
        # Start with "Target 1" and increment until we find an unused name
        counter = 1
        while f"Target {counter}" in existing_names:
            counter += 1
        return f"Target {counter}"

    async def _check_scope(self, host, resolved_hosts, target: BBOTTarget, target_id, asset_scope=None) -> Activity:
        """
        Given a host and its DNS records, check whether it's in scope for a given target

        If the scope status changes, return an activity

        TODO: we may be able to speed this up by using a single RadixTarget cache for all the targets. Then we'd be able to give it a host, and in a single go, have it return all matching targets.

        Args:
            host: the host to check
            resolved_hosts: a dict of DNS records for the host
            target: the target to check against
            target_id: the target ID
            asset_scope: the current scope of the asset (list of current target IDs for the asset,
                         this way we know whether the scope changed)

        Returns:
            Activity: an activity that occurred as a result of the scope check
        """
        in_target_reason = ""
        blacklisted_reason = ""
        resolved_hosts = {k: v for k, v in resolved_hosts.items() if k in ("A", "AAAA")}
        resolved_hosts["SELF"] = [host]
        try:
            # we take the main host and its A/AAAA DNS records into account
            for rdtype, hosts in resolved_hosts.items():
                for host in hosts:
                    # if any of the hosts are blacklisted, abort immediately
                    if target.blacklisted(host):
                        blacklisted_reason = f"{rdtype}->{host}"
                        in_target_reason = ""
                        # break out of the loop
                        raise BlacklistedError
                    # check against whitelist
                    if not in_target_reason:
                        if target.in_target(host):
                            in_target_reason = f"{rdtype}->{host}"
        except BlacklistedError:
            pass

        # if the existing scope wasn't provided, we don't calculate the diff, we just return whether the asset is in scope
        if asset_scope is None:
            if blacklisted_reason:
                return False
            elif in_target_reason:
                return True
            return False

        target_name = (await self._get_target(id=target_id, fields=["name"])).get("name", "")

        if blacklisted_reason:
            scope_after = sorted(set(asset_scope) - set([target_id]))
            # it used to be in-scope, but not anymore
            if scope_after != asset_scope:
                self.log.debug(
                    f"Host {host} used to be in scope for target {target_name} ({target_id}), but is now blacklisted"
                )
                reason = f"blacklisted host {blacklisted_reason}"
                description = f"Host [COLOR]{host}[/COLOR] became out-of-scope for target [COLOR]{target_name}[/COLOR] due to {reason}"
                return self.make_activity(
                    type="ASSET_SCOPE_CHANGED",
                    detail={
                        "change": "out-of-scope",
                        "host": host,
                        "target_id": target_id,
                        "reason": reason,
                        "scope_before": asset_scope,
                        "scope_after": scope_after,
                    },
                    description=description,
                )
        # event is in-scope for this target
        elif in_target_reason:
            scope_after = sorted(set(asset_scope) | set([target_id]))
            # it wasn't in-scope, but now it is
            if scope_after != asset_scope:
                self.log.debug(
                    f"Host {host} used to be out-of-scope for target {target_name} ({target_id}), but is now in-scope"
                )
                reason = f"in-scope host {in_target_reason}"
                description = f"Host [COLOR]{host}[/COLOR] became in-scope for target [COLOR]{target_name}[/COLOR] due to {reason}"
                return self.make_activity(
                    type="NEW_IN_SCOPE_ASSET",
                    detail={
                        "host": host,
                        "target_id": target_id,
                        "reason": reason,
                        "scope_before": asset_scope,
                        "scope_after": scope_after,
                    },
                    description=description,
                )

    async def _get_bbot_target(self, target_id: UUID = None, debounce=5.0) -> BBOTTarget:
        """
        Get the BBOTTarget instance for a given target_id

        Will pull from the cache if it exists and is up to date, otherwise it will create a new one

        debounce is the max age of cached entries to tolerate, to prevent hammering the database with requests
        """
        now = utc_now()
        # check if the target is in the cache
        cached_modified_date, cached_target = self._scope_cache.get(str(target_id), (now, None))
        cache_age = now - cached_modified_date

        if cached_target is not None and cache_age < debounce:
            return cached_target

        # get the target modified date
        target = await self._get_target(id=target_id, fields=["modified"])
        db_modified_date = target["modified"]

        # if the modified date matches, return the cached target
        if cached_modified_date == db_modified_date:
            return cached_target

        # otherwise, refresh the target and return it
        target = await self.get_target(id=target_id)
        self._cache_put(target)
        return self._cache_get(target.id)

    def _cache_put(self, target: Target):
        """
        Put a target into the cache
        """
        self._scope_cache[str(target.id)] = (target.modified, self._bbot_target(target))

    def _cache_get(self, target_id: UUID) -> BBOTTarget:
        """
        Get a target from the cache
        """
        return self._scope_cache[str(target_id)][1]

    async def _refresh_cache(self):
        """
        Refresh the cache for all targets
        """
        for target in await self.get_targets():
            self._cache_put(target)

    def _bbot_target(self, target: Target) -> BBOTTarget:
        """
        Given a target pydantic instance, return a BBOTTarget instance capable of fast host lookups
        """
        return BBOTTarget(
            target=target.target,
            seeds=target.seeds,
            blacklist=target.blacklist,
            strict_dns_scope=target.strict_dns_scope,
        )

    @asynccontextmanager
    async def _handle_duplicate_target(self, target: Target, allow_duplicate_hash: bool = True):
        # see if there are any existing targets with the same name or hash
        if not allow_duplicate_hash:
            if await self.collection.find_one({"hash": target.hash}):
                raise self.BBOTServerValueError(f"Identical target already exists", detail={"hash": target.hash})
        try:
            yield
        except DuplicateKeyError as e:
            key_value = e.details["keyValue"]
            if "name" in key_value:
                raise self.BBOTServerValueError(
                    f'Target with name "{target.name}" already exists', detail={"name": key_value["name"]}
                )
            raise self.BBOTServerValueError(f"Error creating target: {e}")

    async def _get_target(self, id: str = None, hash: str = None, fields: dict[str, Any] = None) -> dict:
        """
        Get a target in raw JSON format from the database
        """
        query = {}
        # if neither id nor hash is provided, try to get the default target
        if id is None and hash is None:
            query["default"] = True
        elif hash is not None:
            query["hash"] = hash
        elif id is not None:
            id = str(id)
            try:
                query["id"] = str(UUID(id))
            except Exception:
                query["name"] = id
        fields = {f: 1 for f in fields} if fields else None
        result = await self.collection.find_one(query, fields)
        if result is None:
            raise self.BBOTServerNotFoundError(f"Target not found.")
        return result
