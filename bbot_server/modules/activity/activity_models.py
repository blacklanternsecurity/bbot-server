import re
import uuid
import logging
from hashlib import sha1
from functools import cached_property
from datetime import datetime, timezone

from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from pydantic import Field as PydanticField

from bbot_server.utils.misc import utc_now
from bbot_server.cli.themes import COLOR, DARK_COLOR
from bbot_server.models.base import HostQuery

remove_rich_color_pattern = re.compile(r"\[([\w ]+)\](.*?)\[/\1\]")

log = logging.getLogger(__name__)


class ActivityQuery(HostQuery):
    """Base request body for activity query/count endpoints."""

    type: str | None = PydanticField(None, description="Filter by activity type")

    async def build(self, applet=None):
        stmt = await super().build(applet)
        model = self._applet.model
        if self.type is not None:
            stmt = stmt.where(model.type == self.type)
        return stmt


class Activity(SQLModel, table=True):
    """
    An Activity is BBOT server's equivalent of an event.

    Activities are emitted whenever an agent connects, a scan starts, a new open port is detected, etc.

    They are usually associated with an asset, and can be traced back to a specific BBOT event.
    """

    __tablename__ = "activities"

    pk: int | None = Field(default=None, primary_key=True)
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), index=True, sa_column_kwargs={"unique": True})
    type: str | None = Field(default=None, index=True)
    host: str | None = Field(default=None, index=True)
    port: int | None = None
    netloc: str | None = None
    url: str | None = None
    timestamp: float = Field(index=True)
    created: float = Field(default_factory=utc_now, index=True)
    archived: bool = Field(default=False, index=True)
    description: str = Field(index=True)
    description_colored: str = ""
    detail: dict | None = Field(default_factory=dict, sa_column=Column(JSONB, server_default="{}"))
    module: str | None = Field(default=None, index=True)
    scan: str | None = Field(default=None, index=True)
    parent_event_uuid: str | None = Field(default=None, index=True)
    parent_event_id: str | None = Field(default=None, index=True)
    parent_scan_run_id: str | None = Field(default=None, index=True)
    parent_activity_id: str | None = Field(default=None, index=True)
    reverse_host: str | None = Field(default=None, index=True)

    def __init__(self, *args, **kwargs):
        # must have a description
        if "description" not in kwargs:
            raise ValueError("description is required")
        # default timestamp is now
        if "timestamp" not in kwargs:
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
        # compute reverse_host
        if self.host is not None and self.reverse_host is None:
            self.reverse_host = self.host[::-1]

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
        # compute reverse_host after setting host
        if self.host is not None and self.reverse_host is None:
            self.reverse_host = self.host[::-1]

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
        # compute reverse_host after potentially setting host
        if self.host is not None and self.reverse_host is None:
            self.reverse_host = self.host[::-1]

    @cached_property
    def hash(self):
        return sha1(f"{self.type}:{self.netloc}:{self.description}".encode()).hexdigest()

    def model_dump(self, *args, mode="json", exclude_none=True, **kwargs):
        return super().model_dump(*args, mode=mode, exclude_none=exclude_none, **kwargs)

    def __eq__(self, other):
        return self.hash == other.hash

    def __hash__(self):
        return hash(self.id)
