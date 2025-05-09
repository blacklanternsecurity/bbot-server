import uuid
from typing import Annotated, Any
from pydantic import UUID4, Field, computed_field

from bbot_server.utils.misc import utc_now
from bbot_server.models.base import BaseBBOTServerModel


class Preset(BaseBBOTServerModel):
    __tablename__ = "presets"
    __user__ = True
    id: Annotated[UUID4, "indexed", "unique"] = Field(default_factory=uuid.uuid4)
    name: Annotated[str, "indexed", "unique"] = Field(default="")
    preset: dict[str, Any]
    created: Annotated[float, "indexed"] = Field(default_factory=utc_now)
    modified: Annotated[float, "indexed"] = Field(default_factory=utc_now)

    @computed_field
    @property
    def description(self) -> str:
        return self.preset.get("description", "")
