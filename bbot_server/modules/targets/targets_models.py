import uuid
from functools import cached_property
from typing import Optional, Annotated
from pydantic import Field, computed_field

from bbot.scanner.target import BBOTTarget
from bbot_server.utils.misc import utc_now
from bbot_server.models.base import BaseBBOTServerModel


class BaseTarget(BaseBBOTServerModel):
    description: str = ""
    target: Optional[list[str]] = []
    seeds: Optional[list[str]] = None
    blacklist: Optional[list[str]] = []
    strict_dns_scope: bool = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bbot_target = BBOTTarget(
            target=self.target, seeds=self.seeds, blacklist=self.blacklist, strict_dns_scope=self.strict_dns_scope
        )
        # self.target = sorted(self.target.inputs)

    @property
    def bbot_target(self):
        return self._bbot_target

    @computed_field
    @cached_property
    def hash(self) -> Annotated[str, "indexed", "unique"]:
        return self.bbot_target.hash.hex()

    @computed_field
    @cached_property
    def target_hash(self) -> Annotated[str, "indexed"]:
        return self._bbot_target.target.hash.hex()

    @computed_field
    @cached_property
    def blacklist_hash(self) -> Annotated[str, "indexed"]:
        return self._bbot_target.blacklist.hash.hex()

    @computed_field
    @cached_property
    def seed_hash(self) -> Annotated[str, "indexed"]:
        return self._bbot_target.seeds.hash.hex()

    @computed_field
    @cached_property
    def scope_hash(self) -> Annotated[str, "indexed"]:
        return self._bbot_target.scope_hash.hex()

    @computed_field
    @cached_property
    def target_size(self) -> int:
        return len(self.bbot_target.target)

    @computed_field
    @cached_property
    def blacklist_size(self) -> int:
        return len(self.bbot_target.blacklist)

    @computed_field
    @cached_property
    def seed_size(self) -> int:
        return 0 if not self.bbot_target._orig_seeds else len(self.bbot_target.seeds)


class Target(BaseTarget):
    __table_name__ = "targets"
    __store_type__ = "user"
    id: Annotated[uuid.UUID, "indexed", "unique"] = Field(default_factory=uuid.uuid4)
    name: Annotated[str, "indexed", "unique"]
    default: Annotated[bool, "indexed"] = False
    created: Annotated[float, "indexed"] = Field(default_factory=utc_now)
    modified: Annotated[float, "indexed"] = Field(default_factory=utc_now)
