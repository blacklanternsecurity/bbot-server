import uuid
from pydantic import UUID4, Field
from typing import Annotated, Any, Optional, Union

from bbot import Preset
from bbot_server.models.base import BaseBBOTServerModel


### TARGETS ###


class BaseTarget(BaseBBOTServerModel):
    name: Annotated[str, "indexed", "unique"]
    description: str = ""
    target: list[str] = []
    whitelist: Union[list[str], None] = None
    blacklist: Union[list[str], None] = None


class Target(BaseTarget):
    __tablename__ = "targets"
    __user__ = True
    id: Annotated[UUID4, "indexed", "unique"] = Field(default_factory=uuid.uuid4)


### SCANS ###


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
    started_at: Annotated[Optional[float], "indexed"] = None
    finished_at: Annotated[Optional[float], "indexed"] = None
    duration_seconds: Optional[float] = None
    duration: Optional[str] = None
