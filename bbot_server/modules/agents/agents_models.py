import uuid
from pydantic import BaseModel, Field
from typing import Annotated, Any, Optional
from bbot_server.models.base import BaseBBOTServerModel


class Agent(BaseBBOTServerModel):
    __table_name__ = "agents"
    __store_type__ = "user"
    id: Annotated[uuid.UUID, "indexed", "unique"] = Field(default_factory=uuid.uuid4)
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
    error: Optional[str] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # if the response is an error, set the error field
        if (not self.error) and self.response.get("status", "success") == "error":
            self.error = self.response.get("message", "")
