import jsondiff
from hashlib import sha1
from copy import deepcopy
from contextlib import suppress
from typing import Annotated, Any, Union, Optional
from pydantic import Field, ValidationError, TypeAdapter

from bbot.models.pydantic import Event
from bbot_server.models.base import BaseBBOTServerModel


class Asset(BaseBBOTServerModel):
    __tablename__ = "assets"

    host: Annotated[str, "indexed"]
    reverse_host: Annotated[Optional[Union[str, None]], "indexed"] = None
    # "fields" contains a variety of custom data fields set by applets
    # the majority of asset data is stored here
    fields: dict[str, Any] = Field(default_factory=dict)

    _field_validator = None
    _type_validators = {}

    def __init__(self, *args, **kwargs):
        if self._field_validator is None:
            raise ValueError("Field validator is not set. Please set Asset._field_validator before using this model.")
        super().__init__(*args, **kwargs)

    def update_field(self, fieldname, value):
        """
        Updates a field of the asset and returns a JSON diff of the changes.
        """
        json_before = deepcopy(self.fields)
        self.fields[fieldname] = value
        diff = jsondiff.diff(json_before, self.fields, marshal=True)
        return diff, json_before.get(fieldname, None), self.fields[fieldname]

    def _get_field(self, fieldname):
        """
        Get the field definition of the given fieldname (for custom fields only).
        """
        try:
            field = self._field_validator.model_fields[fieldname]
        except KeyError:
            raise AttributeError(f"Looked in custom asset fields, but found no attribute '{fieldname}'")
        return field

    def _get_validator(self, fieldname):
        """
        Get the validator associated with the given fieldname (for custom fields only).
        """
        try:
            type_validator = self._type_validators[fieldname]
        except KeyError:
            field = self._get_field(fieldname)
            type_validator = TypeAdapter(field.annotation)
            self._type_validators[fieldname] = type_validator
        return type_validator

    def __getattr__(self, name):
        """
        A convenience method allowing custom data fields to be accessed directly from the asset object.
        """
        with suppress(AttributeError):
            return super().__getattr__(name)

        # first, we make sure the field exists as a declared applet field
        asset_field = self._get_field(name)

        # next, we try and get it from the current asset
        try:
            field_value = self.fields[name]
        except KeyError:
            # if it doesn't exist yet, we use the default factory
            field_value = asset_field.default_factory()

        # finally, we validate the field value against the type validator
        type_validator = self._get_validator(name)
        try:
            field_value = type_validator.validate_python(field_value)
        except ValidationError as e:
            raise ValueError(f"Field '{name}' exists, but is not valid: {e}")
        return field_value


class AssetActivity(BaseBBOTServerModel):
    __tablename__ = "history"
    type: str
    timestamp: float
    description: str
    description_colored: str
    host: Union[str, None] = None
    reverse_host: Annotated[Union[str, None], "indexed"] = None
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
        if self.host:
            if self.type != "NEW_ASSET" and self.fieldname is None:
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
