from pydantic import Field
from typing import Annotated, Any

from bbot_server.models.base import BaseBBOTServerModel


class BBOTStats(BaseBBOTServerModel):
    __tablename__ = "stats"
    key: Annotated[str, "indexed", "unique"]
    value: Annotated[dict[str, Any], "indexed"] = Field(default_factory=dict)
