import re
import uuid
import logging
from hashlib import sha1
from functools import cached_property
from datetime import datetime, timezone

from pydantic import Field, computed_field
from typing import Annotated, Any, Optional

from bbot_server.utils.misc import utc_now
from bbot_server.cli.themes import COLOR, DARK_COLOR
from bbot_server.models.base import HostQuery, BaseHostModel

remove_rich_color_pattern = re.compile(r"\[([\w ]+)\](.*?)\[/\1\]")

log = logging.getLogger(__name__)


class ActivityQuery(HostQuery):
    """Base request body for activity query/count endpoints."""

    type: str | None = Field(None, description="Filter by activity type")


class Activity(BaseHostModel):
    """
    An Activity is BBOT server's equivalent of an event.

    Activities are emitted whenever an agent connects, a scan starts, a new open port is detected, etc.

    They are usually associated with an asset, and can be traced back to a specific BBOT event.
    """

    __store_type__ = "asset"
    __table_name__ = "history"
    # id is a UUID
    id: Annotated[str, "indexed", "unique"] = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: Annotated[float, "indexed"] = Field(
        description="Timestamp matching the event that triggered this activity"
    )
    created: Annotated[float, "indexed"] = Field(
        default_factory=utc_now, description="Time when this activity was created"
    )
    archived: Annotated[bool, "indexed"] = False
    description: Annotated[str, "indexed"]
    description_colored: str = Field(default="")
    detail: dict[str, Any] = {}
    module: Annotated[Optional[str], "indexed"] = None
    scan: Annotated[Optional[str], "indexed"] = None
    host: Annotated[Optional[str], "indexed"] = None
    parent_event_uuid: Annotated[Optional[str], "indexed"] = None
    parent_event_id: Annotated[Optional[str], "indexed"] = None
    parent_scan_run_id: Annotated[Optional[str], "indexed"] = None
    parent_activity_id: Annotated[Optional[str], "indexed"] = None

    def __init__(self, *args, **kwargs):
        # must have a description
        if not "description" in kwargs:
            raise ValueError("description is required")
        # default timestamp is now
        if not "timestamp" in kwargs:
            kwargs["timestamp"] = datetime.now(timezone.utc).timestamp()
        # make a non-colored version of the description
        if "description_colored" not in kwargs:
            description = kwargs["description"]
            # we save the description in two forms - colored and uncolored
            kwargs["description_colored"] = description.replace("DARK_COLOR", DARK_COLOR).replace("COLOR", COLOR)
            kwargs["description"] = remove_rich_color_pattern.sub(r"\2", description)
        event = kwargs.pop("event", None)
        parent_activity = kwargs.pop("parent_activity", None)
        super().__init__(*args, **kwargs)
        if event is not None:
            self.set_event(event)
        if parent_activity is not None:
            self.set_activity(parent_activity)

    def set_event(self, event):
        """
        Copy data from a BBOT event into the activity
        """
        self.parent_event_id = event.id
        self.parent_event_uuid = event.uuid
        self.module = event.module
        self.timestamp = event.timestamp
        self.parent_scan_run_id = event.scan
        if event.host and not self.host:
            self.host = event.host
        if event.port and not self.port:
            self.port = event.port
        if event.netloc and not self.netloc:
            self.netloc = event.netloc
        if event.scan and not self.scan:
            self.scan = event.scan
        # handle url
        event_data_json = getattr(event, "data_json", None)
        if event_data_json is not None:
            url = event_data_json.get("url", None)
            if url is not None:
                self.url = url

    def set_activity(self, activity: "Activity"):
        """
        Copy data from another activity into this one
        """
        self.parent_activity_id = activity.id
        for attr_name in (
            "url",
            "host",
            "port",
            "module",
            "netloc",
            "scan",
            "parent_event_id",
            "parent_event_uuid",
            "parent_scan_run_id",
        ):
            # only copy the attribute if it's not already set on self
            self_attr = getattr(self, attr_name, None)
            activity_attr = getattr(activity, attr_name, None)
            if not self_attr and activity_attr:
                setattr(self, attr_name, activity_attr)

    # @cached_property
    # def id(self):
    #     return f"{self.type}:{self.host}:{self.description}"

    @computed_field
    @property
    def reverse_host(self) -> Annotated[Optional[str], "indexed"]:
        if self.host is not None:
            return self.host[::-1]
        return None

    @cached_property
    def hash(self):
        return sha1(f"{self.type}:{self.netloc}:{self.description}".encode()).hexdigest()

    def __eq__(self, other):
        return self.hash == other.hash
