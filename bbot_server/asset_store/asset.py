import jsondiff
from hashlib import sha1
from copy import deepcopy
from pydantic import BaseModel
from typing import Annotated, Any, Union

from bbot.models.pydantic import Event


class Asset(BaseModel):
    __tablename__ = "assets"

    host: Annotated[str, "indexed"]
    fields: dict[str, Any] = {}

    def update_field(self, fieldname, value):
        """
        Updates a field of the asset and returns a JSON diff of the changes.
        """
        json_before = deepcopy(self.fields)
        self.fields[fieldname] = value
        diff = jsondiff.diff(json_before, self.fields, marshal=True)
        return diff, json_before.get(fieldname, None), self.fields[fieldname]

    def __getattr__(self, name):
        try:
            return self.fields[name]
        except KeyError:
            raise AttributeError(f"'Asset' object has no attribute '{name}'")


class AssetActivity(BaseModel):
    __tablename__ = "history"

    type: str
    timestamp: float
    description: str
    description_colored: str
    host: Union[str, None] = None
    fieldname: Union[str, None] = None
    module: Union[str, None] = None
    event_uuid: Union[str, None] = None
    diff: dict[str, Any] = {}
    before: Union[Any, None] = None
    after: Union[Any, None] = None

    @classmethod
    def create(
        cls,
        type: str,
        asset: Asset,
        event: Event,
        fieldname: str,
        value: Any,
        description: str,
        description_colored: str,
    ):
        diff, before, after = asset.update_field(fieldname, value)
        activity = cls(
            type=type,
            host=asset.host,
            event=event,
            fieldname=fieldname,
            diff=diff,
            before=before,
            after=after,
            description=description,
            description_colored=description_colored,
        )
        return activity

    def __init__(self, *args, **kwargs):
        event = kwargs.get("event", None)
        if event is not None:
            kwargs["host"] = event.host
            kwargs["module"] = event.module
            kwargs["timestamp"] = event.timestamp
            kwargs["event_uuid"] = event.uuid
        super().__init__(*args, **kwargs)
        if self.host and self.type != "NEW_ASSET" and self.fieldname is None:
            raise ValueError("fieldname is required whenever an existing asset is updated")
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
