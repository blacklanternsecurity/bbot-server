import uuid
from functools import cached_property
from typing import Optional, Annotated
from pydantic import Field, computed_field

from bbot.scanner.target import BBOTTarget
from bbot_server.utils.misc import utc_now
from bbot_server.models.base import BaseBBOTServerModel, BaseQuery


class TargetQuery(BaseQuery):
    pass


class BaseTarget(BaseBBOTServerModel):
    """Base class for all target models."""

    description: Annotated[str, "indexed-text"] = Field("", description="Target description")
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bbot_target = BBOTTarget(
            target=self.target, seeds=self.seeds, blacklist=self.blacklist, strict_dns_scope=self.strict_dns_scope
        )
        # self.target = sorted(self.target.inputs)

    @property
    def bbot_target(self):
        return self._bbot_target

    @computed_field(
        description="Hash of the target. This is combined from the target, seeds, and blacklist hashes. Strict scope is also taken into account."
    )
    @cached_property
    def hash(self) -> Annotated[str, "indexed"]:
        return self.bbot_target.hash.hex()

    @computed_field(description="Hash of the target list.")
    @cached_property
    def target_hash(self) -> Annotated[str, "indexed"]:
        return self._bbot_target.target.hash.hex()

    @computed_field(description="Hash of the blacklist.")
    @cached_property
    def blacklist_hash(self) -> Annotated[str, "indexed"]:
        return self._bbot_target.blacklist.hash.hex()

    @computed_field(description="Hash of the seeds.")
    @cached_property
    def seed_hash(self) -> Annotated[str, "indexed"]:
        return self._bbot_target.seeds.hash.hex()

    @computed_field(description="Hash of the scope (target + blacklist + strict scope setting).")
    @cached_property
    def scope_hash(self) -> Annotated[str, "indexed"]:
        return self._bbot_target.scope_hash.hex()

    @computed_field(description="Number of entries in the target list.")
    @cached_property
    def target_size(self) -> int:
        return len(self.bbot_target.target)

    @computed_field(description="Number of entries in the blacklist.")
    @cached_property
    def blacklist_size(self) -> int:
        return len(self.bbot_target.blacklist)

    @computed_field(description="Number of entries in the seeds list.")
    @cached_property
    def seed_size(self) -> int:
        return 0 if not self.bbot_target._orig_seeds else len(self.bbot_target.seeds)


class CreateTarget(BaseTarget):
    """Used for creating a new target."""

    name: Annotated[str, "indexed", "indexed-text", "unique", Field(description="Target name", default="")]
    default: Annotated[
        bool,
        "indexed",
        Field(description="If True, this is the default target. There can only be one default target."),
    ] = False
    allow_duplicate_hash: Annotated[
        bool,
        Field(description="If False, return an error if an identical target already exists"),
    ] = False


class Target(CreateTarget):
    """Used for storing a target in the database."""

    __table_name__ = "targets"
    __store_type__ = "user"
    id: Annotated[uuid.UUID, "indexed", "unique"] = Field(
        default_factory=uuid.uuid4, description="Universally Unique Target ID"
    )
    created: Annotated[float, "indexed"] = Field(
        default_factory=utc_now, description="Timestamp of when the target was created"
    )
    modified: Annotated[float, "indexed"] = Field(
        default_factory=utc_now, description="Timestamp of when the target was last modified"
    )
