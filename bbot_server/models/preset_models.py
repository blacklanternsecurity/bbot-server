import uuid
from typing import Annotated, Any
from pydantic import UUID4, Field, computed_field

from bbot_server.utils.misc import utc_now
from bbot_server.models.base import BaseBBOTServerModel


class Preset(BaseBBOTServerModel):
    __tablename__ = "presets"
    __user__ = True
    id: Annotated[UUID4, "indexed", "unique"] = Field(default_factory=uuid.uuid4)
    preset: dict[str, Any] = Field(default_factory=dict)
    created: Annotated[float, "indexed"] = Field(default_factory=utc_now)
    modified: Annotated[float, "indexed"] = Field(default_factory=utc_now)

    @computed_field
    @property
    def name(self) -> Annotated[str, "indexed", "unique"]:
        return self.preset.get("name", "")

    @name.setter
    def name(self, value: str) -> None:
        self.preset["name"] = value

    @computed_field
    @property
    def description(self) -> Annotated[str, "indexed-text"]:
        return self.preset.get("description", "")

    @description.setter
    def description(self, value: str) -> None:
        self.preset["description"] = value
