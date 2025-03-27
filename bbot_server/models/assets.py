import re
import jsondiff
from hashlib import sha1
from copy import deepcopy
from contextlib import suppress
from functools import cached_property
from datetime import datetime, timezone
from typing import Annotated, Any, Union, Optional
from pydantic import Field, ValidationError, TypeAdapter

from bbot.models.pydantic import Event
from bbot_server.models.base import BaseBBOTServerModel


remove_rich_color_pattern = re.compile(r"\[\[.*?\](.*?)\[/.*?\]\]")


# class Asset(BaseBBOTServerModel):
#     __tablename__ = "assets"

#     host: Annotated[str, "indexed"]
#     reverse_host: Annotated[Optional[Union[str, None]], "indexed"] = None
#     # "fields" contains a variety of custom data fields set by applets
#     # the majority of asset data is stored here
#     fields: dict[str, Any] = Field(default_factory=dict)

#     _field_validator = None
#     _type_validators = {}

#     def __init__(self, *args, **kwargs):
#         if self._field_validator is None:
#             raise ValueError("Field validator is not set. Please set Asset._field_validator before using this model.")
#         super().__init__(*args, **kwargs)

#     def update_field(self, fieldname, value):
#         """
#         Updates a field of the asset and returns a JSON diff of the changes.
#         """
#         json_before = deepcopy(self.fields)
#         self.fields[fieldname] = value
#         diff = jsondiff.diff(json_before, self.fields, marshal=True)
#         return diff, json_before.get(fieldname, None), self.fields[fieldname]

#     def _get_field(self, fieldname):
#         """
#         Get the field definition of the given fieldname (for custom fields only).
#         """
#         try:
#             field = self._field_validator.model_fields[fieldname]
#         except KeyError:
#             raise AttributeError(f"Looked in custom asset fields, but found no attribute '{fieldname}'")
#         return field

#     def _get_validator(self, fieldname):
#         """
#         Get the validator associated with the given fieldname (for custom fields only).
#         """
#         try:
#             type_validator = self._type_validators[fieldname]
#         except KeyError:
#             field = self._get_field(fieldname)
#             type_validator = TypeAdapter(field.annotation)
#             self._type_validators[fieldname] = type_validator
#         return type_validator

#     def __getattr__(self, name):
#         """
#         A convenience method allowing custom data fields to be accessed directly from the asset object.
#         """
#         with suppress(AttributeError):
#             return super().__getattribute__(name)

#         # first, we make sure the field exists as a declared applet field
#         asset_field = self._get_field(name)

#         # next, we try and get it from the current asset
#         try:
#             field_value = self.fields[name]
#         except KeyError:
#             # if it doesn't exist yet, we use the default factory
#             field_value = asset_field.default_factory()

#         # finally, we validate the field value against the type validator
#         type_validator = self._get_validator(name)
#         try:
#             field_value = type_validator.validate_python(field_value)
#         except ValidationError as e:
#             raise ValueError(f"Field '{name}' exists, but is not valid: {e}")
#         return field_value


class AssetActivity(BaseBBOTServerModel):
    """
    An "asset activity" is a record of a change to an asset.

    E.g., a change to an asset's open ports, technologies, etc.
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

    @classmethod
    def from_event(cls, event: Event, **kwargs):
        kwargs["host"] = event.host
        kwargs["netloc"] = event.netloc
        kwargs["module"] = event.module
        kwargs["timestamp"] = event.timestamp
        kwargs["event_uuid"] = event.uuid
        kwargs["event_id"] = event.id
        activity = cls(event=event, **kwargs)
        return activity

    def __init__(self, *args, **kwargs):
        if not "description" in kwargs:
            raise ValueError("description is required")
        if not "timestamp" in kwargs:
            kwargs["timestamp"] = datetime.now(timezone.utc).timestamp()
        description = kwargs["description"]
        # we save the description in two forms - colored and uncolored
        kwargs["description_colored"] = description
        kwargs["description"] = remove_rich_color_pattern.sub(r"\1", description)
        super().__init__(*args, **kwargs)

    @cached_property
    def id(self):
        return f"{self.type}:{self.host}:{self.description}"

    @cached_property
    def hash(self):
        return sha1(self.id.encode()).hexdigest()

    def __eq__(self, other):
        return self.hash == other.hash


class BaseAssetFields(BaseBBOTServerModel):
    """
    Contains a subset of fields which are merged into the main asset.
    """

    def ingest_event(self, event):
        pass

    def diff(self, old) -> list[AssetActivity]:
        return []


class BaseAssetFacet(BaseBBOTServerModel):
    """
    An "asset facet" is a document that describes an asset.

    Unlike the main asset model which contains a summary of all the data,
    a facet contains a certain detail which is too big to be stored in the main asset model.

    For example, the main asset might contain a summary of all the technologies found on the asset,
    but a facet might contain the specific technologies and details about their discovery.

    A facet typically corresponds to an applet.
    """

    host: Annotated[str, "indexed"]
    type: Annotated[Optional[str], "indexed"] = None
    reverse_host: Annotated[Optional[Union[str, None]], "indexed"] = None
    netloc: Annotated[Optional[Union[str, None]], "indexed"] = None
    ignored: bool = False
    archived: bool = False

    def __init__(self, *args, **kwargs):
        if not getattr(self, "__tablename__", None):
            kwargs["type"] = self.__class__.__name__
        super().__init__(*args, **kwargs)

    def _ingest_event(self, event) -> list[AssetActivity]:
        self_before = self.__class__.model_validate(self)
        self.ingest_event(event)
        return self.diff(self_before)

    def ingest_event(self, event):
        """
        Given a BBOT event, update the asset facet.

        E.g., given an OPEN_TCP_PORT event, update the open_ports field to include the new port.
        """
        raise NotImplementedError(f"Must define ingest_event() in {self.__class__.__name__}")

    def diff(self, other) -> list[AssetActivity]:
        """
        Given another facet (typically an older version of the same host), return a list of AssetActivities which describe the new changes.
        """
        raise NotImplementedError(f"Must define diff() in {self.__class__.__name__}")
