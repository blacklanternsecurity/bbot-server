from bbot.models.pydantic import Event as BBOTEvent


class Event(BBOTEvent):
    __table_name__ = "events"
    __store_type__ = "event"
