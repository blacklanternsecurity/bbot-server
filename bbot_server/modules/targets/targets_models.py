import uuid
from typing import Optional, Annotated
from pydantic import Field
from sqlmodel import Field as SQLField
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

from bbot.scanner.target import BBOTTarget
from bbot_server.utils.misc import utc_now
from bbot_server.models.base import BaseBBOTServerModel, BaseQuery, derive


class TargetQuery(BaseQuery):
    """Base request body for targets query/count endpoints."""

    name: str | None = Field(None, description="Filter by target name")
    min_created_timestamp: float | None = Field(None, description="Filter by minimum created timestamp")
    max_created_timestamp: float | None = Field(None, description="Filter by maximum created timestamp")
    min_modified_timestamp: float | None = Field(None, description="Filter by minimum modified timestamp")
    max_modified_timestamp: float | None = Field(None, description="Filter by maximum modified timestamp")

    async def build(self, applet=None):
        stmt = await super().build(applet)
        model = self._applet.model

        if self.name is not None:
            stmt = stmt.where(model.name == self.name)

        if self.min_created_timestamp is not None:
            stmt = stmt.where(model.created >= self.min_created_timestamp)
        if self.max_created_timestamp is not None:
            stmt = stmt.where(model.created <= self.max_created_timestamp)

        if self.min_modified_timestamp is not None:
            stmt = stmt.where(model.modified >= self.min_modified_timestamp)
        if self.max_modified_timestamp is not None:
            stmt = stmt.where(model.modified <= self.max_modified_timestamp)

        return stmt


class BaseTarget(BaseBBOTServerModel):
    """Base class for all target models."""

    name: str = Field(default="", description="Target name")
    default: bool = Field(
        False,
        description="If True, this is the default target. There can only be one default target.",
    )
    description: str = Field("", description="Target description")
    target: Optional[list[str]] = Field(
        default_factory=list,
        description="List of BBOT targets, e.g. domains, IPs, CIDRs, URLs, etc. These determine the scope of the scan. They are also used as seeds if no seeds are provided.",
    )
    seeds: Optional[list[str]] = Field(
        None,
        description="Domains, IPs, CIDRs, URLs, etc. to seed the scan. If not provided, the target list will be used as seeds.",
    )
    blacklist: Optional[list[str]] = Field(
        default_factory=list,
        description="Domains, IPs, CIDRs, URLs, etc. to blacklist from the scan. If a host is blacklisted, it will not be scanned.",
    )
    strict_dns_scope: bool = Field(
        False,
        description="If True, only the exact hosts themselves should be considered in-scope, not their subdomains",
    )


class CreateTarget(BaseTarget):
    """Used for creating a new target."""

    allow_duplicate_hash: bool = Field(
        True,
        description="If False, return an error if an identical target already exists",
    )


class Target(BaseTarget, table=True):
    """Target model — both Pydantic model and SQLAlchemy table."""

    __tablename__ = "targets"

    pk: int | None = SQLField(default=None, primary_key=True)
    id: uuid.UUID = SQLField(
        default_factory=uuid.uuid4,
        index=True,
        sa_column_kwargs={"unique": True},
    )
    # Override list fields with JSONB columns
    name: str = SQLField(default="", index=True, sa_column_kwargs={"unique": True})
    default: bool = SQLField(default=False, index=True)
    target: list | None = SQLField(default_factory=list, sa_column=Column(JSONB, server_default="[]"))
    seeds: list | None = SQLField(default=None, sa_column=Column(JSONB, nullable=True))
    blacklist: list | None = SQLField(default_factory=list, sa_column=Column(JSONB, server_default="[]"))
    # Timestamps
    created: float = SQLField(default_factory=utc_now, index=True)
    modified: float = SQLField(default_factory=utc_now, index=True)
    # Derived hash fields (computed on insert, loaded from DB)
    hash: str | None = SQLField(default=None, index=True)
    target_hash: str | None = None
    blacklist_hash: str | None = None
    seed_hash: str | None = None
    scope_hash: str | None = None
    target_size: int | None = None
    blacklist_size: int | None = None
    seed_size: int | None = None

    def __init__(self, **kwargs):
        # Coerce string id to UUID (SQLModel table=True skips Pydantic validators)
        if "id" in kwargs and isinstance(kwargs["id"], str):
            kwargs["id"] = uuid.UUID(kwargs["id"])
        super().__init__(**kwargs)

    @property
    def bbot_target(self):
        if not hasattr(self, "_bbot_target") or self._bbot_target is None:
            self._bbot_target = BBOTTarget(
                target=self.target, seeds=self.seeds,
                blacklist=self.blacklist, strict_dns_scope=self.strict_dns_scope,
            )
        return self._bbot_target

    @derive("hash")
    def _derive_hash(self):
        return self.bbot_target.hash.hex()

    @derive("target_hash")
    def _derive_target_hash(self):
        return self.bbot_target.target.hash.hex()

    @derive("blacklist_hash")
    def _derive_blacklist_hash(self):
        return self.bbot_target.blacklist.hash.hex()

    @derive("seed_hash")
    def _derive_seed_hash(self):
        return self.bbot_target.seeds.hash.hex()

    @derive("scope_hash")
    def _derive_scope_hash(self):
        return self.bbot_target.scope_hash.hex()

    @derive("target_size")
    def _derive_target_size(self):
        return len(self.bbot_target.target)

    @derive("blacklist_size")
    def _derive_blacklist_size(self):
        return len(self.bbot_target.blacklist)

    @derive("seed_size")
    def _derive_seed_size(self):
        return 0 if not self.bbot_target._orig_seeds else len(self.bbot_target.seeds)
