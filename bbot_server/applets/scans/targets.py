from pydantic import UUID4

from bbot.scanner.target import BBOTTarget

from bbot_server.utils.misc import utc_now
from bbot_server.applets.scans.scan_models import Target
from bbot_server.applets._base import BaseApplet, api_endpoint


class TargetsApplet(BaseApplet):
    name = "Targets"
    description = "scan targets"
    watched_activities = ["TARGET_CREATED", "TARGET_UPDATED", "NEW_ASSET", "NEW_DNS_RECORD", "DELETED_DNS_RECORD"]
    model = Target

    async def setup(self):
        # this holds the BBOTTarget instance for each target
        # enables near-instantaneous scope checks for any host
        self._scope_cache = {}

    async def handle_activity(self, activity):
        """
        Whenever an asset gets created/updated, we evaluate it against the current targets and tag it accordingly

        This lets us easily categorize+query assets by scope

        Similarly, whenever a target is created/updated/deleted, we iterate through all the assets and update them
        """
        if activity.type in ("TARGET_CREATED", "TARGET_UPDATED"):
            for host in await self.root.get_hosts():
                await self.update_scope(host)
        # elif activity.type in ("NEW_ASSET", "NEW_DNS_RECORD", "DELETED_DNS_RECORD"):
        #     await self.update_scope(activity.detail["host"])

    async def update_scope(self, host: str):
        """
        Given a host, evaluate it against all the
        """
        asset = await self.root.assets.get_asset(host)
        for target_id, target_scope in await self.get_scope().items():
            if target_scope.in_scope(host):
                asset.scope = set(asset.scope + [target_id])
            else:
                asset.scope = set(asset.scope) - set([target_id])
        await self.root.assets.update_asset(asset)

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
        self._cache_put(target)
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
        all_scans = await self.parent.get_scans()
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

        # after deleting the target, also delete it from all the assets
        target_id_str = str(id)
        # Remove the target ID from all asset
        await self.root.assets.collection.update_many(
            {"scope": target_id_str},  # Find documents that have this target ID in their scope
            {"$pull": {"scope": target_id_str}},  # Remove this target ID from the scope array
        )

    @api_endpoint("/list", methods=["GET"], summary="List scans")
    async def get_targets(self) -> list[Target]:
        cursor = self.collection.find()
        targets = await cursor.to_list(length=None)
        targets = [Target(**target) for target in targets]
        return targets

    @api_endpoint("/in_scope/{host}", methods=["GET"], summary="Check if a host is in scope")
    async def in_scope(self, host: str, target_id: UUID4 = None) -> bool:
        scope = await self.get_scope()
        try:
            target = scope[target_id]
        except KeyError:
            raise self.BBOTServerNotFoundError(f"Target not found.")
        return target.in_scope(host)

    async def _get_bbot_target(self, target_id: UUID4, lazy=False) -> BBOTTarget:
        """
        Get the BBOTTarget instance for a given target_id

        Will pull from the cache if it exists and is up to date, otherwise it will create a new one

        if lazy is True, don't bother looking in the database for the target modified date, and just return the current cached target
        """
        # check if the target is in the cache
        cached_modified_date, cached_target = self._scope_cache.get(str(target_id), (None, None))

        if cached_target is not None and lazy:
            return cached_target

        # get the target modified date
        db_modified_date = await self.collection.find_one({"id": str(target_id)}, {"modified": 1})
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
