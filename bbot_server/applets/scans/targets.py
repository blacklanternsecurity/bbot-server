from pydantic import UUID4
from typing import Annotated

from bbot.scanner.target import BBOTTarget

from bbot_server.utils.misc import utc_now
from bbot_server.models.activity import Activity
from bbot_server.applets.scans.scan_models import Target
from bbot_server.applets._base import BaseApplet, api_endpoint
from bbot_server.assets.custom_fields import CustomAssetFields


class BlacklistedError(Exception):
    pass


# TODO:
# we already have hashing implemented for targets.
# we should include the target hash alongside its ID on assets,
# this way we know whether the scope is up to date
# we should have a single task for doing this, and automatically cancel or restart it if a new operation comes along
# this enables extremely fast and precise updates whenever a target is updated


class AssetScope(CustomAssetFields):
    scope: Annotated[list[UUID4], "indexed"] = []


class TargetsApplet(BaseApplet):
    name = "Targets"
    description = "scan targets"
    watched_events = ["*"]
    watched_activities = ["TARGET_CREATED", "TARGET_UPDATED", "NEW_ASSET", "NEW_DNS_RECORD", "DELETED_DNS_RECORD"]
    model = Target

    async def setup(self):
        # this holds the BBOTTarget instance for each target
        # enables near-instantaneous scope checks for any hosts
        self._scope_cache = {}
        # this holds an up-to-date list of all the target IDs
        self._target_ids = set()
        self._target_ids_modified = None

    async def handle_event(self, event, asset):
        """
        Whenever a new event comes in, we check its host and all its A/AAAA records against our targets,
        and update its associated asset scope with the matching targets
        """
        activities = []

        if asset is None or event.host is None:
            return

        resolved_hosts = {"SELF": [event.host]}
        dns_children = getattr(event, "dns_children", {})
        for rdtype in ("A", "AAAA"):
            resolved_hosts[rdtype] = dns_children.get(rdtype, [])

        # check event against each of our targets
        for target_id in await self.get_target_ids():
            bbot_target = await self._get_bbot_target(target_id)
            scope_result = self._check_scope(event.host, resolved_hosts, bbot_target, target_id, asset.scope)
            if scope_result is not None:
                scope_result.set_event(event)
                if scope_result.type == "NEW_IN_SCOPE_ASSET":
                    asset.scope = sorted(set(asset.scope) | set([target_id]))
                else:
                    asset.scope = sorted(set(asset.scope) - set([target_id]))
                activities.append(scope_result)
        return activities

    async def handle_activity(self, activity):
        """
        Whenever an asset gets created/updated, we evaluate it against the current targets and tag it accordingly

        This lets us easily categorize+query assets by scope

        Similarly, whenever a target is created/updated/deleted, we iterate through all the assets and update them
        """
        # await self._refresh_cache()
        if activity.type in ("TARGET_CREATED", "TARGET_UPDATED"):
            for target_id in await self.get_target_ids(debounce=0.0):
                target = await self._get_bbot_target(target_id, debounce=0.0)
                for host in await self.root.get_hosts():
                    await self.refresh_scope(host, target, target_id)
        # elif activity.type in ("NEW_ASSET", "NEW_DNS_RECORD", "DELETED_DNS_RECORD"):
        #     await self.update_scope(activity.detail["host"])

    async def refresh_scope(self, host: str, target: BBOTTarget, target_id: UUID4):
        """
        Given a host, evaluate it against all the current targets and tag it with each matching target's ID
        """
        asset = await self.root.assets.collection.find_one({"host": host}, {"scope": 1, "dns_links": 1})
        if asset is None:
            raise self.BBOTServerNotFoundError(f"Asset not found for host {host}")
        asset_scope = [UUID4(target_id) for target_id in asset.get("scope", [])]
        asset_dns_links = asset.get("dns_links", {})
        scope_result = self._check_scope(host, asset_dns_links, target, target_id, asset_scope)
        if scope_result is not None:
            if scope_result.type == "NEW_IN_SCOPE_ASSET":
                asset_scope = sorted(set(asset_scope) | set([target_id]))
            else:
                asset_scope = sorted(set(asset_scope) - set([target_id]))
            await self.root.assets.collection.update_one(
                {"host": host},
                {"$set": {"scope": [str(target_id) for target_id in asset_scope]}},
            )
            await self.emit_activity(scope_result)

    @api_endpoint("/", methods=["GET"], summary="Get a single scan target by its name or id")
    async def get_target(self, name: str = None, id: UUID4 = None) -> Target:
        # if neither name nor id is provided, try to get the default target
        if (name is None) and (id is None):
            target = await self.collection.find_one({"default": True})
            if target is None:
                raise self.BBOTServerNotFoundError(
                    "No default target found. Please create one or specify a target name or id."
                )
        else:
            query = {}
            if name:
                query["name"] = name
            elif id is not None:
                query["id"] = str(id)
            target = await self.collection.find_one(query)
        if not target:
            raise self.BBOTServerNotFoundError(f"Target not found.")
        return Target(**target)

    @api_endpoint("/count", methods=["GET"], summary="Get the number of scan targets")
    async def target_count(self) -> int:
        return await self.collection.count_documents({})

    @api_endpoint("/set_default/{target_id}", methods=["POST"], summary="Set a target as the default target")
    async def set_default_target(self, target_id: UUID4):
        # get target
        target = await self.get_target(id=target_id)
        target.default = True
        await self.collection.update_one({"id": str(target_id)}, {"$set": target.model_dump()})
        # finally, set default=false on all other targets
        await self.collection.update_many({"id": {"$ne": str(target_id)}}, {"$set": {"default": False}})

    @api_endpoint("/create", methods=["POST"], summary="Create a new scan target")
    async def create_target(
        self,
        name: str,
        description: str = "",
        target: list[str] = [],
        whitelist: list[str] = None,
        blacklist: list[str] = None,
    ) -> Target:
        target = Target(name=name, description=description, target=target, whitelist=whitelist, blacklist=blacklist)
        if await self.target_count() == 0:
            target.default = True
        await self.collection.insert_one(target.model_dump())
        # emit an activity to show the target was created
        await self.emit_activity(
            type="TARGET_CREATED",
            detail={"target_id": str(target.id)},
            description=f"Target [dark_orange]{target.name}[/dark_orange] created",
        )
        # update caches
        self._cache_put(target)
        self._target_ids.add(str(target.id))
        self._target_ids_modified = None
        return target

    @api_endpoint("/{id}", methods=["PATCH"], summary="Update a scan target by its id")
    async def update_target(self, id: UUID4, target: Target) -> Target:
        target.id = id
        target.modified = utc_now()
        await self.collection.update_one({"id": str(id)}, {"$set": target.model_dump()})
        # emit an activity to show the target was updated
        await self.emit_activity(
            type="TARGET_UPDATED",
            detail={"target_id": str(target.id)},
            description=f"Target [dark_orange]{target.name}[/dark_orange] updated",
        )
        # reset target
        self._cache_put(target)
        return target

    @api_endpoint("/{id}", methods=["DELETE"], summary="Delete a scan target by its id")
    async def delete_target(self, id: UUID4, new_default_target_id: UUID4 = None) -> None:
        # TODO: abort if the target is still in use by any scans
        all_scans = await self.root.scans.get_scans()
        scans_with_target = [scan for scan in all_scans if scan.target_id == id]
        if scans_with_target:
            raise self.BBOTServerValueError(
                f"Target is still in use by the following scans: {', '.join([str(scan.name) for scan in scans_with_target])}"
            )

        target = await self.get_target(id=id)

        # when we're deleting the default target, we need to set a new one
        if target.default:
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
                        "Must specify a new default target when deleting the default target."
                    )

        target = await self.get_target(id=id)
        await self.collection.delete_one({"id": str(target.id)})

        # set the new default target
        if new_default_target_id is not None:
            await self.set_default_target(new_default_target_id)

        # clear scope cache
        if self._scope_cache is not None:
            self._scope_cache.pop(str(id))

        # clear target ID
        self._target_ids.discard(str(id))

        # after deleting the target, also delete it from all the assets
        target_id_str = str(id)
        # Remove the target ID from all asset
        await self.root.assets.collection.update_many(
            {"scope": target_id_str},  # Find documents that have this target ID in their scope
            {"$pull": {"scope": target_id_str}},  # Remove this target ID from the scope array
        )

    @api_endpoint("/in_scope", methods=["GET"], summary="Check if a host or URL is in scope")
    async def in_scope(self, host: str, target_id: UUID4 = None) -> bool:
        bbot_target = await self._get_bbot_target(target_id)
        return bbot_target.in_scope(host)

    @api_endpoint("/whitelisted", methods=["GET"], summary="Check if a host or URL is whitelisted")
    async def is_whitelisted(self, host: str, target_id: UUID4 = None) -> bool:
        bbot_target = await self._get_bbot_target(target_id)
        return bbot_target.whitelisted(host)

    @api_endpoint("/blacklisted", methods=["GET"], summary="Check if a host or URL is blacklisted")
    async def is_blacklisted(self, host: str, target_id: UUID4 = None) -> bool:
        bbot_target = await self._get_bbot_target(target_id)
        return bbot_target.blacklisted(host)

    @api_endpoint("/list", methods=["GET"], summary="List targets")
    async def get_targets(self) -> list[Target]:
        cursor = self.collection.find()
        targets = await cursor.to_list(length=None)
        targets = [Target(**target) for target in targets]
        return targets

    @api_endpoint("/list_ids", methods=["GET"], summary="List all target IDs")
    async def get_target_ids(self, debounce: float = 5.0) -> list[UUID4]:
        if self._target_ids_modified is None or utc_now() - self._target_ids_modified > debounce:
            self._target_ids = set(await self.collection.distinct("id"))
            self._target_ids_modified = utc_now()
        return [UUID4(target_id) for target_id in self._target_ids]

    def _check_scope(self, host, resolved_hosts, target, target_id, asset_scope) -> Activity:
        """
        Given a host and its DNS records, check whether it's in scope for a given target

        If the scope status changes, return an activity

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
        whitelisted_reason = ""
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
                        whitelisted_reason = ""
                        # break out of the loop
                        raise BlacklistedError
                    # check against whitelist
                    if not whitelisted_reason:
                        if target.whitelisted(host):
                            whitelisted_reason = f"{rdtype}->{host}"
        except BlacklistedError:
            pass

        if blacklisted_reason:
            scope_after = sorted(set(asset_scope) - set([target_id]))
            # it used to be in-scope, but not anymore
            if scope_after != asset_scope:
                reason = f"blacklisted host {blacklisted_reason}"
                description = f"Host [dark_orange]{host}[/dark_orange] became out-of-scope due to {reason}"
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
        elif whitelisted_reason:
            scope_after = sorted(set(asset_scope) | set([target_id]))
            # it wasn't in-scope, but now it is
            if scope_after != asset_scope:
                reason = f"whitelisted host {whitelisted_reason}"
                description = f"Host [dark_orange]{host}[/dark_orange] became in-scope due to {reason}"
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

    async def _get_bbot_target(self, target_id: UUID4 = None, debounce=5.0) -> BBOTTarget:
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

        if target_id is None:
            query = {"default": True}
        else:
            query = {"id": str(target_id)}

        # get the target modified date
        db_modified_date = await self.collection.find_one(query, {"modified": 1})
        if db_modified_date is None:
            raise self.BBOTServerNotFoundError(f"Target not found.")
        db_modified_date = db_modified_date["modified"]

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

    def _cache_get(self, target_id: UUID4) -> BBOTTarget:
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
        return BBOTTarget(
            *target.target,
            whitelist=target.whitelist,
            blacklist=target.blacklist,
            strict_scope=target.strict_dns_scope,
        )
