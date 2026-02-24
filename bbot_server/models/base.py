import re
import logging
from uuid import UUID
from hashlib import sha1
from typing import Union, Optional, Annotated
from pydantic import Field as PydanticField, BaseModel, computed_field
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Index, select, func, text, asc, desc, or_, and_
from sqlalchemy.orm import declared_attr
from sqlalchemy.dialects.postgresql import JSONB

from bbot.core.helpers.misc import make_netloc

from bbot_server.utils.misc import utc_now
from bbot_server.errors import BBOTServerError, BBOTServerValueError

log = logging.getLogger("bbot_server.models")

host_split_regex = re.compile(r"[^a-z0-9]")


def derive(field_name):
    """Mark a method as deriving a stored column value.

    The base __init__ calls all @derive methods after construction.
    Only sets the field if it's currently None (so DB-loaded rows aren't recomputed).
    """
    def decorator(fn):
        fn._derives = field_name
        return fn
    return decorator


class BaseBBOTServerModel(SQLModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._run_derives()

    def _run_derives(self):
        """Auto-compute derived stored fields. Only sets fields that are currently None."""
        for name in dir(type(self)):
            method = getattr(type(self), name, None)
            field = getattr(method, '_derives', None)
            if field and getattr(self, field, None) is None:
                result = method(self)
                if result is not None:
                    setattr(self, field, result)

    def model_dump(self, *args, mode="json", exclude_none=True, **kwargs):
        return super().model_dump(*args, mode=mode, exclude_none=exclude_none, **kwargs)

    def sha1(self, data: str) -> str:
        return sha1(data.encode()).hexdigest()


class BaseHostModel(BaseBBOTServerModel):
    """
    A base model for all BBOT Server models that have a host.

    Provides host, host_parts columns with automatic derivation.
    Subclasses with table=True get these as stored columns.
    """

    @declared_attr
    def __table_args__(cls):
        return (
            Index(f"ix_{cls.__tablename__}_host_reverse", text("reverse(host) text_pattern_ops")),
        )

    host: str = Field(index=True)
    port: int | None = Field(default=None)
    netloc: str | None = Field(default=None)
    url: str | None = Field(default=None)
    host_parts: list | None = Field(default=None, sa_type=JSONB)
    created: float = Field(default_factory=utc_now, index=True)
    modified: float = Field(default_factory=utc_now, index=True)
    ignored: bool = False
    archived: bool = Field(default=False, index=True)

    def __init__(self, **kwargs):
        event = kwargs.pop("event", None)
        super().__init__(**kwargs)
        if event is not None:
            self._set_event(event)
            # Re-run derives since _set_event may have set port/netloc/etc.
            self._run_derives()

    def _set_event(self, event):
        """Copy host/port/url from a BBOT event."""
        if event.host and not self.host:
            self.host = event.host
        if event.port and not self.port:
            self.port = event.port
        if event.netloc and not self.netloc:
            self.netloc = event.netloc
        event_data_json = getattr(event, "data_json", None)
        if event_data_json is not None:
            url = event_data_json.get("url", None)
            if url is not None:
                self.url = url

    @derive("host_parts")
    def _derive_host_parts(self):
        if self.host:
            return host_split_regex.split(self.host)

    @derive("netloc")
    def _derive_netloc(self):
        if self.host and self.port:
            return make_netloc(self.host, self.port)


def _is_jsonb_col(col):
    """Check if a SQLAlchemy column is a JSONB type."""
    from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
    try:
        return isinstance(col.type, PG_JSONB)
    except Exception:
        return False


def _jsonb_contains(col, val):
    """Check if a JSONB array column contains a value, using the @> operator."""
    import json
    return col.op("@>")(func.cast(json.dumps(val), text("jsonb")))


def _jsonb_or_col_regex(col, val):
    """Apply regex match, handling JSONB array columns specially.

    For JSONB array columns (e.g. host_parts), check if ANY element matches.
    For regular columns, use Postgres regex operator directly.
    """
    if _is_jsonb_col(col):
        # JSONB array: EXISTS (SELECT 1 FROM jsonb_array_elements_text(col) AS elem WHERE elem ~ val)
        from sqlalchemy import exists, literal_column
        elem_alias = func.jsonb_array_elements_text(col).alias("_arr_elem")
        return exists(
            select(literal_column("1"))
            .select_from(elem_alias)
            .where(literal_column("_arr_elem").op("~")(val))
        )
    return col.op("~")(val)


def _apply_json_filters(stmt, model, query_dict):
    """
    Translate a MongoDB-style JSON filter dict to SQLAlchemy WHERE clauses.

    Supports a subset of MongoDB operators:
        {"field": value}            -> field = value
        {"field": {"$gt": v}}       -> field > v
        {"field": {"$gte": v}}      -> field >= v
        {"field": {"$lt": v}}       -> field < v
        {"field": {"$lte": v}}      -> field <= v
        {"field": {"$ne": v}}       -> field != v
        {"field": {"$in": [...]}}   -> field IN (...)
        {"field": {"$nin": [...]}}  -> field NOT IN (...)
        {"field": {"$regex": "..."}} -> field ~ '...' (Postgres regex)
        {"field": {"$exists": true}} -> field IS NOT NULL
        {"$and": [...]}             -> AND(...)
        {"$or": [...]}              -> OR(...)
        {"$text": {"$search": "..."}} -> search_vector @@ plainto_tsquery(...)
    """
    conditions = []

    for key, value in query_dict.items():
        if key == "$and":
            sub_conditions = []
            for sub_filter in value:
                sub_stmt = _apply_json_filters(select(model), model, sub_filter)
                sub_conditions.extend(sub_stmt.whereclause.clauses if hasattr(sub_stmt.whereclause, 'clauses') else [sub_stmt.whereclause])
            conditions.append(and_(*sub_conditions))
        elif key == "$or":
            sub_conditions = []
            for sub_filter in value:
                sub_stmt = _apply_json_filters(select(model), model, sub_filter)
                wc = sub_stmt.whereclause
                if wc is not None:
                    sub_conditions.append(wc)
            if sub_conditions:
                conditions.append(or_(*sub_conditions))
        elif key == "$text":
            search_term = value.get("$search", "")
            if search_term and hasattr(model, "search_vector"):
                ts_query = func.plainto_tsquery("simple", search_term.strip())
                conditions.append(model.search_vector.op("@@")(ts_query))
        elif "." in key:
            # JSONB dot-notation: e.g. "data_json.technology" -> data_json['technology']
            parts = key.split(".", 1)
            col = getattr(model, parts[0], None)
            if col is None:
                raise BBOTServerValueError(f"Unknown field: {parts[0]}")
            json_col = col[parts[1]].astext
            if isinstance(value, dict):
                for op, val in value.items():
                    if op == "$gt":
                        conditions.append(json_col > str(val))
                    elif op == "$gte":
                        conditions.append(json_col >= str(val))
                    elif op == "$lt":
                        conditions.append(json_col < str(val))
                    elif op == "$lte":
                        conditions.append(json_col <= str(val))
                    elif op == "$ne":
                        conditions.append(json_col != str(val))
                    elif op == "$eq":
                        conditions.append(json_col == str(val))
                    elif op == "$regex":
                        conditions.append(json_col.op("~")(val))
                    elif op == "$exists":
                        if val:
                            conditions.append(col[parts[1]].isnot(None))
                        else:
                            conditions.append(col[parts[1]].is_(None))
                    else:
                        raise BBOTServerValueError(f"Unsupported query operator for JSONB field: {op}")
            else:
                conditions.append(json_col == str(value))
        elif isinstance(value, dict):
            # operator-based filter on a field
            col = getattr(model, key, None)
            if col is None:
                raise BBOTServerValueError(f"Unknown field: {key}")
            for op, val in value.items():
                if op == "$gt":
                    conditions.append(col > val)
                elif op == "$gte":
                    conditions.append(col >= val)
                elif op == "$lt":
                    conditions.append(col < val)
                elif op == "$lte":
                    conditions.append(col <= val)
                elif op == "$ne":
                    conditions.append(col != val)
                elif op == "$eq":
                    conditions.append(col == val)
                elif op == "$in":
                    conditions.append(col.in_(val))
                elif op == "$nin":
                    conditions.append(~col.in_(val))
                elif op == "$regex":
                    conditions.append(_jsonb_or_col_regex(col, val))
                elif op == "$exists":
                    if val:
                        conditions.append(col.isnot(None))
                    else:
                        conditions.append(col.is_(None))
                else:
                    raise BBOTServerValueError(f"Unsupported query operator: {op}")
        else:
            # simple equality
            col = getattr(model, key, None)
            if col is None:
                raise BBOTServerValueError(f"Unknown field: {key}")
            conditions.append(col == value)

    if conditions:
        stmt = stmt.where(and_(*conditions))
    return stmt


class BaseQuery(BaseModel):
    """
    Base class for representing an HTTP request to a BBOT Server API endpoint.

    Builds SQLAlchemy Select statements instead of MongoDB queries.
    """

    query: dict | None = Field(
        None, description="JSON filter (translated to SQL WHERE clauses)"
    )
    search: str | None = Field(
        None,
        description="A human-friendly text search",
    )
    fields: list[str] | None = Field(
        None, description="Specifies which fields to return in data"
    )
    skip: int | None = Field(None, description="Offset/skip this many rows")
    limit: int | None = Field(None, description="Limit how many results to return")
    sort: list[str | tuple[str, int]] | None = Field(
        None, description="Sort specification: field names or (field, direction) tuples"
    )
    aggregate: list | None = Field(
        None, description="MongoDB-style aggregation pipeline"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # process sort spec: "+field"/"-field" strings or (field, direction) tuples
        if self.sort:
            self.sort = [
                (f.lstrip("+-"), -1 if f.startswith("-") else 1) if isinstance(f, str) else tuple(f) for f in self.sort
            ]
        self._applet = None

    async def build(self, applet=None):
        """
        Build a SQLAlchemy Select statement from the query parameters.
        """
        if applet is not None:
            self._applet = applet
        if not self._applet:
            raise BBOTServerError(f"API query {self.__class__.__name__} is missing its parent applet :(")

        model = self._applet.model
        stmt = select(model)

        # apply JSON filters
        if self.query:
            stmt = _apply_json_filters(stmt, model, self.query)

        # apply search
        if self.search:
            stmt = await self._apply_search(stmt, model)

        # apply sort
        if self.sort:
            for field, direction in self.sort:
                col = getattr(model, field, None)
                if col is not None:
                    stmt = stmt.order_by(desc(col) if direction == -1 else asc(col))

        # apply skip/limit
        if self.skip:
            stmt = stmt.offset(self.skip)
        if self.limit:
            stmt = stmt.limit(self.limit)

        return stmt

    async def _apply_search(self, stmt, model):
        """Apply full-text search to the statement."""
        search_str = self.search.strip().lower()
        if not search_str:
            return stmt
        if hasattr(model, "search_vector"):
            ts_query = func.plainto_tsquery("simple", search_str)
            stmt = stmt.where(model.search_vector.op("@@")(ts_query))
        else:
            # fallback: ILIKE on host
            stmt = stmt.where(model.host.ilike(f"%{search_str}%"))
        return stmt

    async def query_iter(self, applet):
        """Async iterate over query results, yielding model instances."""
        stmt = await self.build(applet)
        async with applet.session() as session:
            result = await session.execute(stmt)
            for row in result.scalars():
                yield row

    async def query_count(self, applet):
        """Count results matching the query."""
        stmt = await self.build(applet)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        async with applet.session() as session:
            result = await session.execute(count_stmt)
            return result.scalar()


class HostQuery(BaseQuery):
    """
    Common query used for anything that has a host.

    Corresponds to BaseHostModel
    """

    host: str | None = Field(None, description="Filter by exact hostname or IP")
    domain: str | None = Field(None, description="Filter by domain (subdomains allowed)")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # AI is dumb and likes to pass in blank strings for stuff
        self.host = self.host or None
        self.domain = self.domain or None

    async def build(self, applet=None):
        stmt = await super().build(applet)
        model = self._applet.model

        # host filter
        if self.host is not None:
            stmt = stmt.where(model.host == self.host)

        # domain filter using reverse(host) for efficient subdomain matching
        if self.domain is not None:
            reversed_domain = self.domain[::-1]
            stmt = stmt.where(
                or_(
                    func.reverse(model.host).like(f"{reversed_domain}.%"),
                    model.host == self.domain,
                )
            )

        return stmt

    async def _apply_search(self, stmt, model):
        """Search host_parts prefixes using reverse(host) for efficient matching."""
        search_str = self.search.strip().lower()
        if not search_str:
            return stmt

        reversed_search = search_str[::-1]
        stmt = stmt.where(
            or_(
                func.reverse(model.host).like(f"{reversed_search}%"),
                model.host == search_str,
            )
        )
        return stmt


class ActiveArchivedQuery(HostQuery):
    archived: bool = Field(False, description="Include archived records")
    active: bool = Field(True, description="Include active records")

    async def build(self, applet=None):
        stmt = await super().build(applet)
        model = self._applet.model

        # archived / active filtering
        if not (self.active and self.archived):
            if not (self.active or self.archived):
                raise BBOTServerValueError("Must query at least one of active or archived")
            stmt = stmt.where(model.archived == self.archived)

        return stmt


class AssetQuery(ActiveArchivedQuery):
    """Common asset query used across Assets, Findings, etc."""

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


class BaseScore:
    """Base class for mapping string levels to numeric scores."""

    levels: dict = {}
    name: str = "score"

    @classmethod
    def to_score(cls, value: Union[str, int]) -> int:
        """Convert a level to its numeric score."""
        if isinstance(value, int):
            if value not in cls.levels.values():
                raise BBOTServerValueError(f'Invalid {cls.name} score: "{value}". Must be between 1 and 5.')
            return value
        if isinstance(value, str):
            value = value.upper()
            if value not in cls.levels:
                raise BBOTServerValueError(
                    f'Invalid {cls.name} string: "{value}". Must be one of {list(cls.levels.keys())}'
                )
            return cls.levels[value]
        raise BBOTServerValueError(f"Invalid level passed in as value: {value}")

    @classmethod
    def to_str(cls, score: int) -> str:
        """Convert a numeric score to its string equivalent."""
        for level, value in cls.levels.items():
            if value == score:
                return level
        raise BBOTServerValueError(f"Invalid {cls.name} score: {score}. Must be between 1 and 5.")
