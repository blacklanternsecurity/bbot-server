import re
import logging
from uuid import UUID
from hashlib import sha1
from typing import Union, Optional, Annotated
from pydantic import Field, BaseModel, computed_field

from bbot.core.helpers.misc import make_netloc
from bbot.models.pydantic import BBOTBaseModel

from bbot_server.utils.misc import utc_now
from bbot_server.errors import BBOTServerError, BBOTServerValueError
from bbot_server.utils.misc import _sanitize_mongo_query, _sanitize_mongo_aggregation

log = logging.getLogger("bbot_server.models")

host_split_regex = re.compile(r"[^a-z0-9]")


class BaseBBOTServerModel(BBOTBaseModel):
    def model_dump(self, *args, mode="json", exclude_none=True, **kwargs):
        return _sanitize_mongo_query(super().model_dump(*args, mode=mode, exclude_none=exclude_none, **kwargs))

    def sha1(self, data: str) -> str:
        return sha1(data.encode()).hexdigest()


class BaseHostModel(BaseBBOTServerModel):
    """
    A base model for all BBOT Server models that have a host, port, netloc, and url

    Inherited by Asset and Activity models.

    Corresponds to BaseQuery
    """

    # TODO: why is id commented out?
    # id: Annotated[str, "indexed", "unique"] = Field(default_factory=lambda: str(uuid.uuid4()))
    type: Annotated[Optional[str], "indexed"] = None
    host: Annotated[str, "indexed"]
    port: Annotated[Optional[int], "indexed"] = None
    netloc: Annotated[Optional[str], "indexed"] = None
    url: Annotated[Optional[str], "indexed"] = None
    created: Annotated[float, "indexed"] = Field(default_factory=utc_now)
    modified: Annotated[float, "indexed"] = Field(default_factory=utc_now)
    ignored: bool = False
    archived: bool = False

    def __init__(self, *args, **kwargs):
        event = kwargs.pop("event", None)
        super().__init__(*args, **kwargs)
        if self.host and self.port:
            self.netloc = make_netloc(self.host, self.port)
        if event is not None:
            self.set_event(event)

    def set_event(self, event):
        """
        Copy data from a BBOT event into the asset
        """
        if event.host and not self.host:
            self.host = event.host
        if event.port and not self.port:
            self.port = event.port
        if event.netloc and not self.netloc:
            self.netloc = event.netloc
        # handle url
        event_data_json = getattr(event, "data_json", None)
        if event_data_json is not None:
            url = event_data_json.get("url", None)
            if url is not None:
                self.url = url

    @computed_field
    @property
    def reverse_host(self) -> Annotated[str, "indexed"]:
        if not self.host:
            return ""
        return self.host[::-1]

    @computed_field
    @property
    def host_parts(self) -> Annotated[list[str], "indexed"]:
        if not self.host:
            return []
        return host_split_regex.split(self.host)


class BaseAssetFacet(BaseHostModel):
    """
    An "asset facet" is a database object that contains data about an asset.

    Unlike the main asset model which contains a summary of all the data,
    a facet contains a certain detail which is too big to be stored in the main asset model.

    For example, the main asset might contain a summary of all the technologies found on the asset,
    but a facet might contain the specific technologies and details about their discovery.

    A facet typically corresponds to an applet.
    """

    # scope is an array of target IDs, which are dynamically maintained as new scan data arrives, or as targets are created/updated.
    scope: Annotated[list[UUID], "indexed"] = []

    # unless overridden, all asset facets are stored in the asset store
    __store_type__ = "asset"
    __table_name__ = "assets"

    def __init__(self, *args, **kwargs):
        kwargs["type"] = self.__class__.__name__
        super().__init__(*args, **kwargs)


class BaseQuery(BaseModel):
    """
    Base class for representing an HTTP request to a BBOT Server API endpoint

    Easily extendable by adding more query parameters, etc.
    """

    query: dict | None = Field(
        None, description="The Mongo filter, a Mongo compatible query in the form of a Python dict"
    )
    search: str | None = Field(
        None,
        description="A human-friendly text search",
    )
    fields: list[str] | None = Field(
        None, description="The Mongo projection, specifies which fields to return in data"
    )
    skip: int | None = Field(None, description="Offset/skip this many documents")
    limit: int | None = Field(None, description="Limit how much results to return")
    sort: list[str] | tuple[str, int] | None = Field(
        None, description="The Mongo sort, specifies which fields to sort by or a tuple specifying desc or asc"
    )
    aggregate: list[dict] | None = Field(
        None,
        description="The Mongo aggregate, a list of Mongo compatible aggregation operations (each a Python dict)",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # process fields
        self.fields = {f: 1 for f in self.fields} if self.fields else None
        # process sort spec: "+field"/"-field" strings or (field, direction) tuples
        if self.sort:
            self.sort = [
                (f.lstrip("+-"), -1 if f.startswith("-") else 1) if isinstance(f, str) else tuple(f) for f in self.sort
            ]
        self._applet = None
        self._mongo_cursor = None

    async def build(self, applet=None):
        """
        Given the current attribute values on the model, build the MongoDB query

        The applet is passed in here, in case during the build a secondary query is needed
        """
        if applet is not None:
            self._applet = applet
        if not self._applet:
            raise BBOTServerError(f"API query {self.__class__.__name__} is missing its parent applet :(")

        # base query
        query = dict(self.query or {})

        # search
        if self.search:
            search_query = await self.build_search_query()
            if search_query:
                query = {"$and": [query, search_query]}

        return query

    async def build_search_query(self):
        """
        Given a search term, construct a human-friendly search against multiple fields.
        """
        search_str = self.search.strip().lower()
        if not search_str:
            return None
        return {"$text": {"$search": search_str}}

    async def mongo_iter(self, applet, collection=None):
        """
        Lazy iterator over a Mongo collection with BBOT-specific filters and aggregation
        """
        self._applet = applet
        cursor = await self._make_mongo_cursor(collection=collection)
        async for asset in cursor:
            yield asset

    async def mongo_count(self, applet, collection=None):
        query = await self.build(applet)
        if collection is None:
            collection = self._applet.collection
        sanitized_query = _sanitize_mongo_query(query)
        return await collection.count_documents(sanitized_query)

    async def _make_mongo_cursor(self, collection=None):
        """Build a MongoDB cursor for querying, with optional aggregation pipeline."""
        if self._mongo_cursor is not None:
            return self._mongo_cursor
        query = await self.build()
        sanitized_query = _sanitize_mongo_query(query)

        # collection defaults to self.collection
        if collection is None:
            collection = self._applet.collection

        # if we don't have a default collection and none was passed in, raise an error
        if collection is None:
            raise BBOTServerError(f"Collection is not set for {self._applet.name}")

        log.info(f"Querying {collection.name}: query={sanitized_query}, fields={self.fields}")

        if self.aggregate:
            aggregate = _sanitize_mongo_aggregation(self.aggregate)
            pipeline = [{"$match": query}] + aggregate
            if self.limit is not None:
                pipeline.append({"$limit": self.limit})
            return await collection.aggregate(pipeline)

        cursor = collection.find(query, self.fields)
        if self.sort:
            cursor = cursor.sort(self.sort)
        if self.skip is not None:
            cursor = cursor.skip(self.skip)
        if self.limit is not None:
            cursor = cursor.limit(self.limit)
        self._mongo_cursor = cursor
        return cursor


class HostQuery(BaseQuery):
    """
    Common asset query used for anything that has a host

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
        query = await super().build(applet)

        # host filter
        if ("host" not in query) and (self.host is not None):
            query["host"] = self.host
        # domain filter
        if ("reverse_host" not in query) and (self.domain is not None):
            reversed_host = re.escape(self.domain[::-1])
            # Match exact domain or subdomains (with dot separator)
            query["reverse_host"] = {"$regex": f"^{reversed_host}(\\.|$)"}

        return query

    async def build_search_query(self):
        """
        Given a search term, construct a human-friendly search against multiple fields.
        """
        search_str = self.search.strip().lower()
        if not search_str:
            return None
        search_str_escaped = re.escape(search_str)
        return {
            "$or": [
                {"$text": {"$search": search_str}},
                {"host_parts": {"$regex": f"^{search_str_escaped}"}},
                {"host": {"$regex": f"^{search_str_escaped}"}},
                {"reverse_host": {"$regex": f"^{re.escape(search_str[::-1])}"}},
            ]
        }


class AssetQuery(HostQuery):
    """Common asset query used across Assets, Findings, Events, Technologies, etc."""

    target_id: str | None = Field(None, description="Filter by target name or ID")
    archived: bool = Field(False, description="Include archived records")
    active: bool = Field(True, description="Include active records")
    # force a certain type of asset
    _force_asset_type = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_id = self.target_id or None

    async def build(self, applet=None):
        query = await super().build(applet)
        # target_id filtering
        if ("scope" not in query) and (self.target_id is not None):
            target_query_kwargs = {}
            if self.target_id != "DEFAULT":
                target_query_kwargs["id"] = self.target_id
            target = await self._applet.root.targets._get_target(**target_query_kwargs, fields=["id"])
            if target is not None:
                query["scope"] = target["id"]
        # archived / active filtering
        # if both active and archived are true, we don't need to filter anything, because we are returning all assets
        if not (self.active and self.archived) and ("archived" not in query):
            # if both are false, we need to raise an error
            if not (self.active or self.archived):
                raise BBOTServerValueError("Must query at least one of active or archived")
            # only one should be true
            query["archived"] = {"$eq": self.archived}
        if self._force_asset_type:
            query["type"] = self._force_asset_type
        return query


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
