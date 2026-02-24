from uuid import UUID
from sqlalchemy import select, func, exists, literal_column, asc, desc
from pydantic import Field

from bbot_server.models.base import HostQuery, AssetQuery
from bbot_server.utils.misc import _sanitize_mongo_query, _sanitize_mongo_aggregation
from bbot_server.errors import BBOTServerValueError


class AssetOnlyQuery(HostQuery):
    """Query for the hosts lookup table. No archived/active filtering since Host is minimal."""

    target_id: str | UUID | None = Field(None, description="Filter by target name or ID")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_id = self.target_id or None
        if self.target_id is not None:
            self.target_id = str(self.target_id)

    async def build(self, applet=None):
        stmt = await super().build(applet)
        model = self._applet.model

        # target_id filtering via host_targets table
        if self.target_id is not None:
            from bbot_server.db.tables import HostTarget
            target_query_kwargs = {}
            if self.target_id != "DEFAULT":
                target_query_kwargs["id"] = self.target_id
            target = await self._applet.root.targets._get_target(**target_query_kwargs, fields=["id"])
            if target is not None:
                target_id = target["id"] if isinstance(target, dict) else target.id
                stmt = stmt.where(model.host.in_(
                    select(HostTarget.host).where(HostTarget.target_id == str(target_id))
                ))

        return stmt


class AdvancedAssetQuery(AssetQuery):
    """Advanced asset query with aggregation and MongoDB-compatible querying."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Sanitize query and aggregate
        if self.query:
            self.query = _sanitize_mongo_query(self.query)
        if self.aggregate:
            self.aggregate = _sanitize_mongo_aggregation(self.aggregate)

        # Query dict overrides parameters
        if self.query:
            if "host" in self.query:
                self.host = None
            if "host" in self.query or "reverse_host" in self.query:
                self.domain = None

    async def _apply_search(self, stmt, model):
        """Search by prefix matching on host_parts array elements."""
        search_str = self.search.strip().lower()
        if not search_str:
            return stmt

        if hasattr(model, "host_parts"):
            elem_alias = func.jsonb_array_elements_text(model.host_parts).alias("_arr_elem")
            stmt = stmt.where(
                exists(
                    select(literal_column("1"))
                    .select_from(elem_alias)
                    .where(literal_column("_arr_elem").op("LIKE")(f"{search_str}%"))
                )
            )
        else:
            stmt = stmt.where(model.host.ilike(f"%{search_str}%"))
        return stmt

    async def aggregate_iter(self, applet):
        """Execute a MongoDB-style aggregation pipeline translated to SQL."""
        model = applet.model

        group_stage = None
        sort_stage = None

        for stage in self.aggregate:
            for key, spec in stage.items():
                if key == "$group":
                    group_stage = spec
                elif key == "$sort":
                    sort_stage = spec

        if group_stage is None:
            return

        # Parse _id (GROUP BY column)
        group_by_expr = group_stage["_id"]
        if isinstance(group_by_expr, str) and group_by_expr.startswith("$"):
            col_name = group_by_expr[1:]
            group_col = getattr(model, col_name)
        else:
            raise BBOTServerValueError(f"Unsupported $group _id expression: {group_by_expr}")

        # Build SELECT columns: _id + accumulators
        columns = [group_col.label("_id")]
        for field_name, acc_spec in group_stage.items():
            if field_name == "_id":
                continue
            if isinstance(acc_spec, dict):
                for op, val in acc_spec.items():
                    if op == "$sum":
                        if val == 1:
                            columns.append(func.count().label(field_name))
                        elif isinstance(val, str) and val.startswith("$"):
                            columns.append(func.sum(getattr(model, val[1:])).label(field_name))
                    elif op == "$avg":
                        if isinstance(val, str) and val.startswith("$"):
                            columns.append(func.avg(getattr(model, val[1:])).label(field_name))

        # Build base WHERE from existing filters (active/archived, domain, etc.)
        # Temporarily disable skip/limit for the base query
        saved_skip, saved_limit = self.skip, self.limit
        self.skip, self.limit = None, None
        base_stmt = await self.build(applet)
        self.skip, self.limit = saved_skip, saved_limit

        # Build the aggregation query
        stmt = select(*columns).select_from(model.__table__)
        if base_stmt.whereclause is not None:
            stmt = stmt.where(base_stmt.whereclause)
        stmt = stmt.group_by(group_col)

        # Apply sort
        if sort_stage:
            for field_name, direction in sort_stage.items():
                if direction == -1:
                    stmt = stmt.order_by(desc(field_name))
                else:
                    stmt = stmt.order_by(asc(field_name))

        async with applet.session() as session:
            result = await session.execute(stmt)
            for row in result.mappings():
                yield dict(row)
