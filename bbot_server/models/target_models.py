import uuid
from pydantic import UUID4, Field
from typing import Annotated, Union

from bbot.scanner.target import BBOTTarget
from bbot_server.utils.misc import utc_now
from bbot_server.models.base import BaseBBOTServerModel


class BaseTarget(BaseBBOTServerModel):
    description: str = ""
    seeds: list[str] = []
    whitelist: Union[list[str], None] = None
    blacklist: Union[list[str], None] = None
    strict_dns_scope: bool = False
    hash: Annotated[str, "indexed", "unique"] = ""
    scope_hash: Annotated[str, "indexed"] = ""
    seed_hash: Annotated[str, "indexed"] = ""
    whitelist_hash: Annotated[str, "indexed"] = ""
    blacklist_hash: Annotated[str, "indexed"] = ""
    seed_size: int = 0
    whitelist_size: int = 0
    blacklist_size: int = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bbot_target = BBOTTarget(
            *self.seeds, whitelist=self.whitelist, blacklist=self.blacklist, strict_dns_scope=self.strict_dns_scope
        )
        self.hash = self.bbot_target.hash.hex()
        self.scope_hash = self.bbot_target.scope_hash.hex()
        self.seed_hash = self.bbot_target.seeds.hash.hex()
        self.whitelist_hash = self.bbot_target.whitelist.hash.hex()
        self.blacklist_hash = self.bbot_target.blacklist.hash.hex()
        self.seed_size = len(self.bbot_target.seeds)
        self.whitelist_size = 0 if not self.bbot_target._orig_whitelist else len(self.bbot_target.whitelist)
        self.blacklist_size = len(self.bbot_target.blacklist)

    @property
    def bbot_target(self):
        return self._bbot_target


class Target(BaseTarget):
    __tablename__ = "targets"
    __user__ = True
    id: Annotated[UUID4, "indexed", "unique"] = Field(default_factory=uuid.uuid4)
    name: Annotated[str, "indexed", "unique"]
    default: Annotated[bool, "indexed"] = False
    created: Annotated[float, "indexed"] = Field(default_factory=utc_now)
    modified: Annotated[float, "indexed"] = Field(default_factory=utc_now)
