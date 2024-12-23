from pydantic import BaseModel
from typing import Annotated, Any

from .modules import ASSET_MODULES


class AssetHistoryEntry(BaseModel):
    timestamp: float
    event_uuid: str


class Asset(BaseModel):
    host: Annotated[str, "indexed"]
    history: dict[str, AssetHistoryEntry] = {}
    extra_fields: dict[str, Any] = {}

    def absorb_event(self, event):
        for module in ASSET_MODULES.values():
            module.absorb_event(self, event)

    def archive_event(self, event):
        for module in ASSET_MODULES.values():
            module.archive_event(self, event)

    def add_history_entry(self, description, timestamp, event_uuid):
        if not description in self.history:
            self.history[description] = AssetHistoryEntry(timestamp=timestamp, event_uuid=event_uuid)
