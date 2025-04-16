import uuid
from pydantic import UUID4, Field
from typing import Annotated, Any, Optional, Union

from bbot import Preset
from bbot.scanner.target import BBOTTarget
from bbot_server.utils.misc import utc_now
from bbot_server.models.base import BaseBBOTServerModel

### TARGETS ###


class BaseTarget(BaseBBOTServerModel):
    name: Annotated[str, "indexed", "unique"]
    description: str = ""
    target: list[str] = []
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
            *self.target, whitelist=self.whitelist, blacklist=self.blacklist, strict_scope=self.strict_dns_scope
        )
        self.hash = self.bbot_target.hash.hex()
        self.scope_hash = self.bbot_target.scope_hash.hex()
        self.seed_hash = self.bbot_target.seeds.hash.hex()
        self.whitelist_hash = self.bbot_target.whitelist.hash.hex()
        self.blacklist_hash = self.bbot_target.blacklist.hash.hex()
        self.seed_size = len(self.bbot_target.seeds)
        self.whitelist_size = len(self.bbot_target.whitelist)
        self.blacklist_size = len(self.bbot_target.blacklist)

    @property
    def bbot_target(self):
        return self._bbot_target


class Target(BaseTarget):
    __tablename__ = "targets"
    __user__ = True
    id: Annotated[UUID4, "indexed", "unique"] = Field(default_factory=uuid.uuid4)
    default: Annotated[bool, "indexed"] = False
    created: Annotated[float, "indexed"] = Field(default_factory=utc_now)
    modified: Annotated[float, "indexed"] = Field(default_factory=utc_now)


class BaseScan(BaseBBOTServerModel):
    name: Annotated[str, "indexed", "unique"]
    preset: dict[str, Any] = {}


class ScanDBEntry(BaseScan):
    __tablename__ = "scans"
    __user__ = True

    id: Annotated[UUID4, "indexed", "unique"] = Field(default_factory=uuid.uuid4)
    target_id: Annotated[UUID4, "indexed"]

    def make_preset(self):
        preset = Preset(**self.preset)
        target_preset = Preset(*self.target, whitelist=self.whitelist, blacklist=self.blacklist, scan_name=self.name)
        preset.merge(target_preset)
        return preset


class ScanResponse(BaseScan):
    id: Annotated[UUID4, "indexed", "unique"] = Field(default_factory=lambda: f"SCAN:{uuid.uuid4()}")
    target: Target


### SCAN RUNS ###


class ScanRun(BaseBBOTServerModel):
    __tablename__ = "scan_runs"
    __user__ = True

    id: Annotated[UUID4, "indexed", "unique"] = Field(default_factory=lambda: f"SCAN:{uuid.uuid4()}")
    name: Annotated[str, "indexed"]
    status: Annotated[str, "indexed"] = "QUEUED"
    target: BaseTarget
    agent_id: Annotated[Union[UUID4, None], "indexed"] = None
    parent_scan_id: Annotated[UUID4, "indexed"]
    preset: dict[str, Any]
    seed_with_current_assets: bool = False
    started_at: Annotated[Optional[float], "indexed"] = None
    finished_at: Annotated[Optional[float], "indexed"] = None
    duration_seconds: Optional[float] = None
    duration: Optional[str] = None
