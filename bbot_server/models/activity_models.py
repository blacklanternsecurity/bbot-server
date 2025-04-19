import re
from hashlib import sha1
from pydantic import Field
from functools import cached_property
from datetime import datetime, timezone
from typing import Annotated, Any, Union

from bbot_server.cli.themes import COLOR, DARK_COLOR
from bbot_server.models.base import BaseBBOTServerModel

remove_rich_color_pattern = re.compile(r"\[(\w+)\](.*?)\[/\1\]")


class Activity(BaseBBOTServerModel):
    """
    An Activity is BBOT server's equivalent of an event.

    Activities are emitted whenever an agent connects, a scan starts, a new open port is detected, etc.

    They are usually associated with a asset, and can be traced back to a specific BBOT event.
    """

    __tablename__ = "history"
    type: str
    timestamp: float
    description: str
    description_colored: str = Field(default="")
    detail: dict[str, Any] = {}
    host: Union[str, None] = None
    netloc: Union[str, None] = None
    reverse_host: Annotated[Union[str, None], "indexed"] = None
    module: Union[str, None] = None
    event_uuid: Union[str, None] = None
    event_id: Union[str, None] = None

    def __init__(self, *args, **kwargs):
        if not "description" in kwargs:
            raise ValueError("description is required")
        if not "timestamp" in kwargs:
            kwargs["timestamp"] = datetime.now(timezone.utc).timestamp()
        if "description_colored" not in kwargs:
            description = kwargs["description"]
            # we save the description in two forms - colored and uncolored
            kwargs["description_colored"] = description.replace("DARK_COLOR", DARK_COLOR).replace("COLOR", COLOR)
            kwargs["description"] = remove_rich_color_pattern.sub(r"\2", description)
        event = kwargs.pop("event", None)
        super().__init__(*args, **kwargs)
        if event is not None:
            self.set_event(event)

    def set_event(self, event):
        self.event_id = event.id
        self.event_uuid = event.uuid
        self.module = event.module
        self.timestamp = event.timestamp
        if not self.host:
            self.host = event.host
        if not self.netloc:
            self.netloc = event.netloc

    @cached_property
    def id(self):
        return f"{self.type}:{self.host}:{self.description}"

    @cached_property
    def hash(self):
        return sha1(self.id.encode()).hexdigest()

    def __eq__(self, other):
        return self.hash == other.hash
