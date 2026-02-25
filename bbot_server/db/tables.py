"""
SQLModel table definitions for PostgreSQL.

Host and HostTarget live here as core infrastructure tables.
Module-specific tables (Finding, Event, Activity, etc.) live in their module's *_models.py.
"""

import re
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Index, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB

from bbot_server.models.base import BaseBBOTServerModel, derive
from bbot_server.utils.misc import utc_now

host_split_regex = re.compile(r"[^a-z0-9]")


class Host(BaseBBOTServerModel, table=True):
    """Host lookup table with derived fields for efficient querying."""
    __tablename__ = "hosts"
    __table_args__ = (
        Index("ix_hosts_host_reverse", text("reverse(host) text_pattern_ops")),
    )

    pk: int | None = Field(default=None, primary_key=True)
    host: str = Field(index=True, sa_column_kwargs={"unique": True})
    host_parts: list | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    reverse_host: str | None = Field(default=None, index=True)
    archived: bool = Field(default=False, index=True)
    @derive("host_parts")
    def _derive_host_parts(self):
        if self.host:
            return host_split_regex.split(self.host)

    @derive("reverse_host")
    def _derive_reverse_host(self):
        if self.host:
            return self.host[::-1]


class HostTarget(SQLModel, table=True):
    """Normalized host -> target mapping. One row per (host, target_id) pair."""
    __tablename__ = "host_targets"
    __table_args__ = (UniqueConstraint("host", "target_id"),)

    pk: int | None = Field(default=None, primary_key=True)
    host: str = Field(index=True)
    target_id: str = Field(index=True)
    created: float = Field(default_factory=utc_now)


class ScanTable(SQLModel, table=True):
    __tablename__ = "scans"

    pk: int | None = Field(default=None, primary_key=True)
    id: str = Field(index=True, sa_column_kwargs={"unique": True})
    name: str = Field(index=True, sa_column_kwargs={"unique": True})
    description: str | None = None
    status_code: int = Field(default=0, index=True)
    status: str = Field(default="QUEUED", index=True)
    agent_id: str | None = Field(default=None, index=True)
    target: dict | None = Field(default_factory=dict, sa_column=Column(JSONB, server_default="{}"))
    preset: dict | None = Field(default_factory=dict, sa_column=Column(JSONB, server_default="{}"))
    seed_with_current_assets: bool = False
    created: float = Field(default_factory=utc_now, index=True)
    started_at: float | None = None
    finished_at: float | None = None
    duration_seconds: float | None = None
    duration: str | None = None
