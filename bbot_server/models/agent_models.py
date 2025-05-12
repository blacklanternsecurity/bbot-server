import uuid
from typing import Annotated, Any, Optional
from bbot_server.models.base import BaseBBOTServerModel
from pydantic import BaseModel, Field, UUID4, computed_field


class Agent(BaseBBOTServerModel):
    __tablename__ = "agents"
    id: Annotated[UUID4, "indexed", "unique"] = Field(default_factory=uuid.uuid4)
    name: Annotated[str, "indexed", "unique"]
    description: str
    connected: Annotated[bool, "indexed"] = False
    status: Annotated[str, "indexed"] = "OFFLINE"
    current_scan_id: Annotated[Optional[str], "indexed"] = None
    last_seen: Annotated[Optional[float], "indexed"] = None


class AgentCommand(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    command: str
    kwargs: dict[str, Any]


class AgentResponse(BaseModel):
    request_id: Optional[str] = None
    response: dict[str, Any] = {}

    @computed_field
    @property
    def error(self) -> Optional[str]:
        if self.response.get("status", "success") == "error":
            return self.response.get("message", "")
        return ""
