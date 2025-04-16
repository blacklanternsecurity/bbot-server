import uuid
from pydantic import UUID4, Field
from typing import Annotated, Any, Optional, Union

from bbot_server.utils.misc import utc_now
from bbot_server.models.base import BaseBBOTServerModel
from bbot_server.models.target_models import BaseTarget, Target

### SCANS ###


class BaseScan(BaseBBOTServerModel):
    name: Annotated[str, "indexed", "unique"]
    preset: dict[str, Any] = {}
    created: Annotated[float, "indexed"] = Field(default_factory=utc_now)
    modified: Annotated[float, "indexed"] = Field(default_factory=utc_now)


class ScanDBEntry(BaseScan):
    __tablename__ = "scans"
    __user__ = True

    id: Annotated[UUID4, "indexed", "unique"] = Field(default_factory=uuid.uuid4)
    target_id: Annotated[UUID4, "indexed"]


class ScanResponse(BaseScan):
    id: Annotated[UUID4, "indexed", "unique"] = Field(default_factory=lambda: f"SCAN:{uuid.uuid4()}")
    target: Target


### SCAN RUNS ###


class ScanRun(BaseBBOTServerModel):
    __tablename__ = "scan_runs"
    __user__ = True

    id: Annotated[str, "indexed", "unique"] = Field(default_factory=lambda: f"SCAN:{uuid.uuid4()}")
    name: Annotated[str, "indexed"]
    status: Annotated[str, "indexed"] = "QUEUED"
    target: BaseTarget
    agent_id: Annotated[Union[UUID4, None], "indexed"] = None
    parent_scan_id: Annotated[Optional[UUID4], "indexed"] = None
    preset: dict[str, Any]
    seed_with_current_assets: bool = False
    started_at: Annotated[Optional[float], "indexed"] = None
    finished_at: Annotated[Optional[float], "indexed"] = None
    duration_seconds: Optional[float] = None
    duration: Optional[str] = None
