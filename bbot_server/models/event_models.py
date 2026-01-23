from bbot.models.pydantic import Event as BBOTEvent
from pydantic import Field

from bbot_server.models.base import BaseRequestBody, CommonFilterFields, QueryRequestBody


class BaseEventsRequestBody(CommonFilterFields):
    """Base request body for events query/count endpoints."""

    min_timestamp: float | None = Field(None, description="Filter by minimum timestamp")
    max_timestamp: float | None = Field(None, description="Filter by maximum timestamp")


class QueryEventsRequestBody(BaseEventsRequestBody, QueryRequestBody):
    pass


class CountEventsRequestBody(BaseEventsRequestBody, BaseRequestBody):
    pass


class Event(BBOTEvent):
    __table_name__ = "events"
    __store_type__ = "event"
