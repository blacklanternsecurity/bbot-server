import re

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

        if "type" not in query and self.type is not None:
            query["type"] = self.type

        return query

    async def build_search_query(self):
        """
        Build search query for events using regex (no text index required).
        Searches across type and host fields.
        All patterns are left-anchored for index efficiency.

        Note: Events don't have host_parts/reverse_host (those are on HostModel/AssetModel).
        """
        search_str = self.search.strip().lower()
        if not search_str:
            return None
        search_str_escaped = re.escape(search_str)
        return {
            "$or": [
                {"type": {"$regex": f"^{search_str_escaped.upper()}"}},
                {"host": {"$regex": f"^{search_str_escaped}"}},
            ]
        }


class EventModel(Event):
    __table_name__ = "events"
    __store_type__ = "event"
