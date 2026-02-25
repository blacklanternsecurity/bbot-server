from sqlmodel import SQLModel, Field
from sqlalchemy import Column, or_
from sqlalchemy.dialects.postgresql import JSONB
from pydantic import Field as PydanticField

from bbot_server.utils.misc import utc_now
from bbot_server.models.base import ActiveArchivedQuery


class EventsQuery(ActiveArchivedQuery):
    """Base request body for events query/count endpoints."""

    min_timestamp: float | None = PydanticField(None, description="Filter by minimum timestamp")
    max_timestamp: float | None = PydanticField(None, description="Filter by maximum timestamp")
    scan: str | None = PydanticField(None, description="Filter by BBOT scan ID")
    type: str | None = PydanticField(None, description="Filter by BBOT event type (e.g. DNS_NAME, IP_ADDRESS, FINDING, etc.)")

    async def build(self, applet=None):
        stmt = await super().build(applet)
        model = self._applet.model

        if self.min_timestamp is not None:
            stmt = stmt.where(model.timestamp >= self.min_timestamp)
        if self.max_timestamp is not None:
            stmt = stmt.where(model.timestamp <= self.max_timestamp)
        if self.scan is not None:
            stmt = stmt.where(model.scan == str(self.scan))
        if self.type is not None:
            stmt = stmt.where(model.type == self.type)

        return stmt

    async def _apply_search(self, stmt, model):
        search_str = self.search.strip().lower()
        if not search_str:
            return stmt
        stmt = stmt.where(or_(
            model.type.ilike(f"{search_str.upper()}%"),
            model.host.ilike(f"{search_str}%"),
        ))
        return stmt


class Event(SQLModel, table=True):
    __tablename__ = "events"

    pk: int | None = Field(default=None, primary_key=True)
    uuid: str = Field(index=True, sa_column_kwargs={"unique": True})
    id: str = Field(index=True)
    type: str = Field(index=True)
    scope_description: str = ""
    data: str | None = Field(default=None, index=True)
    data_json: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    host: str | None = Field(default=None, index=True)
    port: int | None = None
    netloc: str | None = None
    resolved_hosts: list | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    dns_children: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    web_spider_distance: int = 10
    scope_distance: int = 10
    scan: str = Field(index=True)
    timestamp: float = Field(index=True)
    inserted_at: float | None = Field(default_factory=utc_now, index=True)
    parent: str = Field(default="", index=True)
    parent_uuid: str = Field(default="", index=True)
    tags: list | None = Field(default_factory=list, sa_column=Column(JSONB, server_default="[]"))
    module: str | None = Field(default=None, index=True)
    module_sequence: str | None = None
    discovery_context: str = ""
    discovery_path: list | None = Field(default_factory=list, sa_column=Column(JSONB, server_default="[]"))
    parent_chain: list | None = Field(default_factory=list, sa_column=Column(JSONB, server_default="[]"))
    archived: bool = Field(default=False, index=True)
    reverse_host: str | None = Field(default=None, index=True)

    def get_data(self):
        if self.data_json is not None:
            return self.data_json
        return self.data

    def model_dump(self, *args, mode="json", exclude_none=True, **kwargs):
        return super().model_dump(*args, mode=mode, exclude_none=exclude_none, **kwargs)

    def __hash__(self):
        return hash(self.uuid)

    def __eq__(self, other):
        return self.uuid == getattr(other, "uuid", None)
