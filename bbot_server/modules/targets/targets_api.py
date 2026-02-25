from uuid import UUID
from contextlib import asynccontextmanager
from sqlalchemy import select, func, delete as sa_delete
from sqlalchemy.exc import IntegrityError
from bbot.scanner.target import BBOTTarget

from bbot_server.utils.misc import utc_now
from bbot_server.db.tables import HostTarget
from bbot_server.applets.base import BaseApplet, api_endpoint
from bbot_server.modules.activity.activity_models import Activity
from bbot_server.modules.targets.targets_models import Target, CreateTarget, TargetQuery


class BlacklistedError(Exception):
    pass


class TargetsApplet(BaseApplet):
    name = "Targets"
    description = "scan targets"
    watched_events = ["*"]
    watched_activities = ["TARGET_CREATED", "TARGET_UPDATED"]
    attach_to = "scans"
    model = Target

    async def setup(self):
        self._scope_cache = {}
        self._target_ids = set()
        self._target_ids_modified = None
        return True, ""

    async def handle_event(self, event, host):
        activities = []
        if host is None or event.host is None:
            return
        dns_children = getattr(event, "dns_children", {})
        current_target_ids = await self._get_host_target_ids(host)
        for target_id in await self.get_target_ids():
            bbot_target = await self._get_bbot_target(target_id)
            scope_result = await self._check_scope(event.host, dns_children, bbot_target, target_id, current_target_ids)
            if scope_result is not None:
                scope_result.set_event(event)
                if scope_result.type == "NEW_IN_SCOPE_ASSET":
                    await self._add_host_target(host, str(target_id))
                    current_target_ids = sorted(set(current_target_ids) | {target_id})
                else:
                    await self._remove_host_target(host, str(target_id))
                    current_target_ids = sorted(set(current_target_ids) - {target_id})
                activities.append(scope_result)
        return activities

    async def handle_activity(self, activity, host=None):
        self.log.debug(f"Target created or updated. Refreshing asset scope")
        target_ids = await self.get_target_ids(debounce=0.0)
        for target_id in target_ids:
            target = await self._get_bbot_target(target_id, debounce=0.0)
            for _host in await self.root.get_hosts():
                await self.refresh_asset_scope(_host, target, target_id, emit_activity=True)
        return []

    async def refresh_asset_scope(self, host: str, target: BBOTTarget, target_id: UUID, emit_activity: bool = False):
        self.log.debug(f"Refreshing asset scope for host {host}")
        current_target_ids = await self._get_host_target_ids(host)
        dns_children = await self._get_dns_children(host)
        scope_result = await self._check_scope(host, dns_children, target, target_id, current_target_ids)
        scope_result_type = getattr(scope_result, "type", None)
        if scope_result_type == "NEW_IN_SCOPE_ASSET":
            await self._add_host_target(host, str(target_id))
        elif scope_result is not None:
            await self._remove_host_target(host, str(target_id))
        if emit_activity and scope_result:
            await self.emit_activity(scope_result)

    async def _add_host_target(self, host: str, target_id: str):
        """Add a host -> target mapping."""
        ht = HostTarget(host=host, target_id=target_id)
        try:
            async with self.session() as session:
                session.add(ht)
                await session.commit()
        except IntegrityError:
            pass  # already exists

    async def _remove_host_target(self, host: str, target_id: str):
        """Remove a host -> target mapping."""
        async with self.session() as session:
            stmt = sa_delete(HostTarget).where(
                HostTarget.host == host, HostTarget.target_id == target_id
            )
            await session.execute(stmt)
            await session.commit()

    async def _get_dns_children(self, host: str) -> dict:
        """Get merged dns_children for a host from all its events."""
        from bbot_server.modules.events.events_models import Event
        merged = {}
        async with self.session() as session:
            stmt = select(Event.dns_children).where(
                Event.host == host,
                Event.dns_children.isnot(None),
            )
            result = await session.execute(stmt)
            for (dc,) in result.all():
                if dc:
                    for rdtype, hosts in dc.items():
                        merged.setdefault(rdtype, []).extend(hosts)
        # deduplicate
        return {k: list(set(v)) for k, v in merged.items()}

    async def _get_host_target_ids(self, host: str) -> list:
        """Get all target IDs for a given host from host_targets table."""
        async with self.session() as session:
            stmt = select(HostTarget.target_id).where(HostTarget.host == host)
            result = await session.execute(stmt)
            return sorted([UUID(row[0]) for row in result.all()])

    @api_endpoint(
        "/",
        methods=["GET"],
        summary="Get a single scan target by its name, id, or hash. If no ID or hash is provided, the default target is returned.",
    )
    async def get_target(self, id: str = None, hash: str = None) -> Target:
        return await self._get_target_row(id=id, hash=hash)

    @api_endpoint("/count", methods=["POST"], summary="Get the number of scan targets")
    async def count_targets(self, query: TargetQuery | None = None) -> int:
        return await query.query_count(self)

    @api_endpoint("/set_default/{id}", methods=["POST"], summary="Set a target as the default target")
    async def set_default_target(self, id: str):
        target = await self._get_target_row(id=id)
        await self._update({"id": target.id}, {"default": True})
        # set default=false on all other targets
        async with self.session() as session:
            from sqlalchemy import update
            stmt = update(Target).where(Target.id != target.id).values(default=False)
            await session.execute(stmt)
            await session.commit()

    @api_endpoint("/create", methods=["POST"], summary="Create a new scan target")
    async def create_target(self, target: CreateTarget) -> Target:
        if not target.target and not target.seeds:
            raise self.BBOTServerValueError("Must provide at least one seed or target entry")
        if not target.name:
            target.name = await self.get_available_target_name()
        db_target = Target(**target.model_dump(exclude={"allow_duplicate_hash"}))
        if await self.count_targets() == 0:
            db_target.default = True
        async with self._handle_duplicate_target(db_target, allow_duplicate_hash=target.allow_duplicate_hash):
            await self._insert(db_target)
        # if target is the default target, set all others to not be default
        if db_target.default:
            async with self.session() as session:
                from sqlalchemy import update
                stmt = update(Target).where(Target.id != db_target.id).values(default=False)
                await session.execute(stmt)
                await session.commit()
        await self.emit_activity(
            type="TARGET_CREATED",
            detail={"target_id": str(db_target.id), "hash": db_target.hash, "scope_hash": db_target.scope_hash},
            description=f"Target [COLOR]{db_target.name}[/COLOR] created",
        )
        self._cache_put(db_target)
        self._target_ids.add(str(db_target.id))
        self._target_ids_modified = None
        return db_target

    @api_endpoint("/{id}", methods=["PATCH"], summary="Update a scan target by its id")
    async def update_target(self, id: UUID, target: Target, allow_duplicate_hash=True) -> Target:
        target.id = id
        target.modified = utc_now()
        async with self._handle_duplicate_target(target, allow_duplicate_hash):
            d = target.model_dump()
            d = {k: v for k, v in d.items() if k != "pk"}
            await self._update({"id": id}, d)
        if target.default:
            async with self.session() as session:
                from sqlalchemy import update
                stmt = update(Target).where(Target.id != target.id).values(default=False)
                await session.execute(stmt)
                await session.commit()
        await self.emit_activity(
            type="TARGET_UPDATED",
            detail={"target_id": str(target.id)},
            description=f"Target [COLOR]{target.name}[/COLOR] updated",
        )
        self._cache_put(target)
        return target

    @api_endpoint("/copy", methods=["POST"], summary="Create a duplicate of a target")
    async def copy_target(self, id: str, name: str = None) -> Target:
        target = await self._get_target_row(id=id)
        if not name:
            name = target.name + " Copy"
        target_copy = await self.create_target(
            CreateTarget(
                name=name,
                description=target.description,
                target=target.target or [],
                seeds=target.seeds,
                blacklist=target.blacklist or [],
                strict_dns_scope=target.strict_dns_scope,
            )
        )
        return target_copy

    @api_endpoint("/", methods=["DELETE"], summary="Delete a scan target by its id")
    async def delete_target(self, id: str, new_default_target_id: str = None) -> None:
        target = await self._get_target_row(id=id)
        target_id = target.id

        if target.default:
            if new_default_target_id is None:
                num_targets = await self.count_targets()
                if num_targets == 2:
                    async with self.session() as session:
                        stmt = select(Target).where(Target.default == False)
                        result = await session.execute(stmt)
                        other_target = result.scalar_one_or_none()
                        if other_target:
                            new_default_target_id = other_target.id
                elif num_targets > 2:
                    raise self.BBOTServerValueError(
                        "Cannot delete the default target without specifying a new default target."
                    )

        await self._delete(id=target_id)

        if new_default_target_id is not None:
            await self.set_default_target(new_default_target_id)

        if self._scope_cache is not None:
            self._scope_cache.pop(str(target_id), None)
        self._target_ids.discard(str(target_id))

        # Remove target from host_targets table
        async with self.session() as session:
            stmt = sa_delete(HostTarget).where(HostTarget.target_id == str(target_id))
            await session.execute(stmt)
            await session.commit()

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
        async with self.session() as session:
            result = await session.execute(select(Target))
            return list(result.scalars().all())

    @api_endpoint(
        "/query",
        methods=["POST"],
        type="http_stream",
        response_model=dict,
        summary="List targets with customizeable fields and optional pagination",
    )
    async def query_targets(self, query: TargetQuery | None = None):
        async for row in query.query_iter(self):
            d = row.model_dump()
            if query.fields:
                d = {k: v for k, v in d.items() if k in query.fields}
                d["_id"] = None  # backward compat
            yield d

    @api_endpoint("/list_ids", methods=["GET"], summary="List all target IDs")
    async def get_target_ids(self, debounce: float = 5.0) -> list[UUID]:
        if self._target_ids_modified is None or utc_now() - self._target_ids_modified > debounce:
            async with self.session() as session:
                result = await session.execute(select(Target.id))
                self._target_ids = set(row[0] for row in result.all())
            self._target_ids_modified = utc_now()
        return [UUID(str(target_id)) for target_id in self._target_ids]

    async def get_available_target_name(self) -> str:
        async with self.session() as session:
            result = await session.execute(select(Target.name))
            existing_names = {row[0] for row in result.all()}
        counter = 1
        while f"Target {counter}" in existing_names:
            counter += 1
        return f"Target {counter}"

    async def _check_scope(self, host, resolved_hosts, target: BBOTTarget, target_id, asset_scope=None) -> Activity:
        in_target_reason = ""
        blacklisted_reason = ""
        resolved_hosts = {k: v for k, v in resolved_hosts.items() if k in ("A", "AAAA")}
        resolved_hosts["SELF"] = [host]
        try:
            for rdtype, hosts in resolved_hosts.items():
                for host in hosts:
                    if target.blacklisted(host):
                        blacklisted_reason = f"{rdtype}->{host}"
                        in_target_reason = ""
                        raise BlacklistedError
                    if not in_target_reason:
                        if target.in_target(host):
                            in_target_reason = f"{rdtype}->{host}"
        except BlacklistedError:
            pass

        if asset_scope is None:
            if blacklisted_reason:
                return False
            elif in_target_reason:
                return True
            return False

        target_row = await self._get_target_row(id=target_id)
        target_name = target_row.name if target_row else ""

        if blacklisted_reason:
            scope_after = sorted(set(asset_scope) - set([target_id]))
            if scope_after != asset_scope:
                reason = f"blacklisted host {blacklisted_reason}"
                description = f"Host [COLOR]{host}[/COLOR] became out-of-scope for target [COLOR]{target_name}[/COLOR] due to {reason}"
                return self.make_activity(
                    type="ASSET_SCOPE_CHANGED",
                    detail={"change": "out-of-scope", "host": host, "target_id": target_id, "reason": reason, "scope_before": asset_scope, "scope_after": scope_after},
                    description=description,
                )
        elif in_target_reason:
            scope_after = sorted(set(asset_scope) | set([target_id]))
            if scope_after != asset_scope:
                reason = f"in-scope host {in_target_reason}"
                description = f"Host [COLOR]{host}[/COLOR] became in-scope for target [COLOR]{target_name}[/COLOR] due to {reason}"
                return self.make_activity(
                    type="NEW_IN_SCOPE_ASSET",
                    detail={"host": host, "target_id": target_id, "reason": reason, "scope_before": asset_scope, "scope_after": scope_after},
                    description=description,
                )
        else:
            scope_after = sorted(set(asset_scope) - set([target_id]))
            if scope_after != asset_scope:
                reason = "target was edited"
                description = f"Host [COLOR]{host}[/COLOR] became out-of-scope for target [COLOR]{target_name}[/COLOR] because {reason}"
                return self.make_activity(
                    type="ASSET_SCOPE_CHANGED",
                    detail={"change": "out-of-scope", "host": host, "target_id": target_id, "reason": reason, "scope_before": asset_scope, "scope_after": scope_after},
                    description=description,
                )

    async def _get_bbot_target(self, target_id: UUID = None, debounce=5.0) -> BBOTTarget:
        now = utc_now()
        cached_modified_date, cached_target = self._scope_cache.get(str(target_id), (now, None))
        cache_age = now - cached_modified_date
        if cached_target is not None and cache_age < debounce:
            return cached_target
        target = await self._get_target_row(id=target_id)
        db_modified_date = target.modified
        if cached_modified_date == db_modified_date:
            return cached_target
        self._cache_put(target)
        return self._cache_get(target.id)

    def _cache_put(self, target: Target):
        self._scope_cache[str(target.id)] = (target.modified, target.bbot_target)

    def _cache_get(self, target_id: UUID) -> BBOTTarget:
        return self._scope_cache[str(target_id)][1]

    async def _refresh_cache(self):
        for target in await self.get_targets():
            self._cache_put(target)

    @asynccontextmanager
    async def _handle_duplicate_target(self, target, allow_duplicate_hash=True):
        if not allow_duplicate_hash:
            async with self.session() as session:
                stmt = select(Target).where(Target.hash == target.hash).limit(1)
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()
            if existing:
                raise self.BBOTServerValueError(f"Identical target already exists", detail={"hash": target.hash})
        try:
            yield
        except IntegrityError as e:
            error_str = str(e.orig) if hasattr(e, 'orig') else str(e)
            if "name" in error_str or "targets_name_key" in error_str:
                raise self.BBOTServerValueError(
                    f'Target with name "{target.name}" already exists', detail={"name": target.name}
                )
            raise self.BBOTServerValueError(f"Error creating target: {e}")

    async def _get_target_row(self, id: str = None, hash: str = None) -> Target:
        """Get a target from the database."""
        async with self.session() as session:
            stmt = select(Target)
            if id is None and hash is None:
                stmt = stmt.where(Target.default == True)
            elif hash is not None:
                stmt = stmt.where(Target.hash == hash)
            elif id is not None:
                id = str(id)
                try:
                    uuid_str = str(UUID(id))
                    stmt = stmt.where(Target.id == uuid_str)
                except (ValueError, AttributeError):
                    stmt = stmt.where(Target.name == id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
        if row is None:
            msg = f"Target not found"
            if id or hash:
                raise self.BBOTServerNotFoundError(msg)
            else:
                self.log.debug(msg)
        return row

    # Backward compat: _get_target returns a dict (used by query classes)
    async def _get_target(self, id: str = None, hash: str = None, fields: list[str] = None) -> dict:
        row = await self._get_target_row(id=id, hash=hash)
        if row is None:
            return None
        d = row.model_dump()
        if fields:
            d = {k: v for k, v in d.items() if k in fields}
        return d
