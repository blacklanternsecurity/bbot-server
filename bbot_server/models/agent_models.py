import uuid
from pydantic import BaseModel, Field, UUID4
from typing import Annotated, Any, Optional, Union
from bbot_server.models.base import BaseBBOTServerModel


class Agent(BaseBBOTServerModel):
    __tablename__ = "agents"
    id: Annotated[UUID4, "indexed", "unique"] = Field(default_factory=uuid.uuid4)
    name: Annotated[str, "indexed", "unique"]
    description: str
    connected: Annotated[bool, "indexed"] = False
    status: Annotated[str, "indexed"] = "OFFLINE"
    current_scan_id: Annotated[Union[str, None], "indexed"] = None
    last_seen: Annotated[Union[float, None], "indexed"] = None


class AgentCommand(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    command: str
    kwargs: dict[str, Any]


class AgentResponse(BaseModel):
    request_id: Optional[str] = None
    response: dict[str, Any] = {}
    error: Optional[str] = None
