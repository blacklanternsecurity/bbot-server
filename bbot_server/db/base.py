import logging

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, String, Float, Boolean, Text, Integer, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy import Computed
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from bbot_server.utils.misc import utc_now

log = logging.getLogger("bbot_server.db.base")


class BBOTServerModel(SQLModel):
    """Abstract base for all bbot-server SQLModel models."""
    class Config:
        arbitrary_types_allowed = True


class BaseHostModel(BBOTServerModel):
    """Base for models with host/port/netloc."""
    host: str = Field(index=True)
    port: int | None = Field(default=None, index=True)
    netloc: str | None = Field(default=None, index=True)
    url: str | None = Field(default=None, index=True)
    reverse_host: str | None = Field(
        default=None,
        sa_column=Column(String, Computed("reverse(host)"), nullable=True)
    )
    created: float = Field(default_factory=utc_now, index=True)
    modified: float = Field(default_factory=utc_now, index=True)
    ignored: bool = False
    archived: bool = Field(default=False, index=True)
