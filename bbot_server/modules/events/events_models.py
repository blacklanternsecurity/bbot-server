from bbot.models.pydantic import Event
from pydantic import Field

from bbot_server.models.base import ActiveArchivedQuery


class EventsQuery(ActiveArchivedQuery):
    """Base request body for events query/count endpoints."""

    min_timestamp: float | None = Field(None, description="Filter by minimum timestamp")
    max_timestamp: float | None = Field(None, description="Filter by maximum timestamp")
    scan: str | None = Field(None, description="Filter by BBOT scan ID")
    type: str | None = Field(None, description="Filter by BBOT event type (e.g. DNS_NAME, IP_ADDRESS, FINDING, etc.)")

    async def build(self, applet=None):
        query = await super().build(applet)

        # timestamps
        if "timestamp" not in query and (self.min_timestamp is not None or self.max_timestamp is not None):
            query["timestamp"] = {}
            if self.min_timestamp is not None:
                query["timestamp"]["$gte"] = self.min_timestamp
            if self.max_timestamp is not None:
                query["timestamp"]["$lte"] = self.max_timestamp

        if "scan" not in query and self.scan is not None:
            query["scan"] = str(self.scan)

        if not "type" in query and self.type is not None:
            query["type"] = self.type

        return query


class EventModel(Event):
    __table_name__ = "events"
    __store_type__ = "event"
