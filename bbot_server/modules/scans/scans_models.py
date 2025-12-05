import uuid
from typing import Annotated, Optional
from pydantic import Field, computed_field

from bbot.constants import get_scan_status_name, SCAN_STATUS_CODES

from bbot_server.models.base import BaseBBOTServerModel
from bbot_server.modules.presets.presets_models import Preset
from bbot_server.modules.targets.targets_models import Target
from bbot_server.utils.misc import utc_now, timestamp_to_human


class Scan(BaseBBOTServerModel):
    __table_name__ = "scans"
    __store_type__ = "user"

    id: Annotated[str, "indexed", "unique"] = Field(default_factory=lambda: f"SCAN:{uuid.uuid4()}")
    name: Annotated[str, "indexed", "unique"]
    description: Annotated[Optional[str], "indexed"] = None
    status_code: Annotated[int, "indexed", Field(ge=min(SCAN_STATUS_CODES), le=max(SCAN_STATUS_CODES))] = 0
    agent_id: Annotated[Optional[uuid.UUID], "indexed"] = None
    target: Target
    preset: Preset
    seed_with_current_assets: bool = False
    created: Annotated[float, "indexed"] = Field(default_factory=utc_now)
    started_at: Annotated[Optional[float], "indexed"] = None
    finished_at: Annotated[Optional[float], "indexed"] = None
    duration_seconds: Optional[float] = None
    duration: Optional[str] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.description:
            self.description = f"Scan '{self.name}' queued against target '{self.target.name}' with preset '{self.preset.name}' at {timestamp_to_human(self.created)}"

    @computed_field
    @property
    def status(self) -> Annotated[str, "indexed"]:
        return get_scan_status_name(self.status_code)
