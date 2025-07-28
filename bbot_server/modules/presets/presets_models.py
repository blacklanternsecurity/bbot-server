import uuid
from typing import Annotated, Any
from pydantic import Field, computed_field, field_validator

from bbot_server.utils.misc import utc_now
from bbot_server.models.base import BaseBBOTServerModel


class Preset(BaseBBOTServerModel):
    __tablename__ = "presets"
    __user__ = True
    id: Annotated[uuid.UUID, "indexed", "unique"] = Field(default_factory=uuid.uuid4)
    preset: dict[str, Any] = Field(default_factory=dict)
    created: Annotated[float, "indexed"] = Field(default_factory=utc_now)
    modified: Annotated[float, "indexed"] = Field(default_factory=utc_now)

    @field_validator("preset")
    @classmethod
    def sanitize_preset(cls, v: dict[str, Any]) -> dict[str, Any]:
        # remote target information
        for value in ("target", "targets", "whitelist", "blacklist"):
            v.pop(value, None)
        # remove strict scope setting (this is stored in the target)
        config = v.pop("config", {})
        if config:
            scope_config = config.pop("scope", {})
            if scope_config:
                scope_config.pop("strict", None)
                config["scope"] = scope_config
            v["config"] = config
        return v

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
