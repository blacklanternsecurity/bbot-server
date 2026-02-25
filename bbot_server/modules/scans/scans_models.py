import uuid
from typing import Annotated, Optional
from pydantic import Field, computed_field

from bbot.constants import get_scan_status_name, SCAN_STATUS_CODES

from sqlalchemy import or_

from bbot_server.models.base import BaseBBOTServerModel, BaseQuery
from bbot_server.modules.presets.presets_models import Preset
from bbot_server.modules.targets.targets_models import Target
from bbot_server.utils.misc import utc_now, timestamp_to_human


class ScanQuery(BaseQuery):
    """Base request body for scans query/count endpoints."""

    name: str | None = Field(None, description="Filter by scan name")
    status: str | None = Field(None, description="Filter by scan status")
    target_id: str | None = Field(None, description="Filter by target ID or name")
    agent_id: str | None = Field(None, description="Filter by agent ID")
    min_created_timestamp: float | None = Field(None, description="Filter by minimum created timestamp")
    max_created_timestamp: float | None = Field(None, description="Filter by maximum created timestamp")

    async def build(self, applet=None):
        stmt = await super().build(applet)
        model = self._applet.model

        if self.name is not None:
            stmt = stmt.where(model.name == self.name)

        if self.status is not None:
            stmt = stmt.where(model.status == self.status)

        if self.agent_id is not None:
            stmt = stmt.where(model.agent_id == self.agent_id)

        # target_id filtering - scans store target as JSONB with id/name keys
        if self.target_id is not None:
            stmt = stmt.where(
                or_(
                    model.target["id"].astext == self.target_id,
                    model.target["name"].astext == self.target_id,
                )
            )

        if self.min_created_timestamp is not None:
            stmt = stmt.where(model.created >= self.min_created_timestamp)
        if self.max_created_timestamp is not None:
            stmt = stmt.where(model.created <= self.max_created_timestamp)

        return stmt


class Scan(BaseBBOTServerModel):
    __table_name__ = "scans"
    __store_type__ = "user"

    id: Annotated[str, "indexed", "unique"] = Field(default_factory=lambda: f"SCAN:{uuid.uuid4()}")
    name: Annotated[str, "indexed", "indexed-text", "unique"]
    description: Annotated[Optional[str], "indexed", "indexed-text"] = None
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
