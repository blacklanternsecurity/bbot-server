from hashlib import sha1
from pydantic import BaseModel
from typing import Annotated, Any


class AssetActivity(BaseModel):
    __tablename__ = "history"

    type: str
    host: str
    timestamp: float
    description: str
    description_colored: str

    def __init__(self, *args, **kwargs):
        event = kwargs.get("event", None)
        if event is not None:
            kwargs["host"] = event.host
            kwargs["module"] = event.module
            kwargs["timestamp"] = event.timestamp
            kwargs["event_uuid"] = event.uuid
        super().__init__(*args, **kwargs)
        self._id = None
        self._hash = None

    @property
    def id(self):
        if self._id is None:
            self._id = f"{self.type}:{self.host}:{self.description}"
        return self._id

    @property
    def hash(self):
        if self._hash is None:
            self._hash = sha1(self.id.encode()).hexdigest()
        return self._hash

    def __eq__(self, other):
        return self.hash == other.hash


class Asset(BaseModel):
    __tablename__ = "assets"

    host: Annotated[str, "indexed"]
    extra_fields: dict[str, Any] = {}

    def __getattr__(self, name):
        try:
            return self.extra_fields[name]
        except KeyError:
            raise AttributeError(f"'Asset' object has no attribute '{name}'")
