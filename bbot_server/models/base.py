import logging
from hashlib import sha1
from typing import get_origin, get_args, Annotated

from bbot.models.pydantic import BBOTBaseModel
from bbot_server.utils.misc import _sanitize_mongo_operators

log = logging.getLogger("bbot_server.models")


class BaseBBOTServerModel(BBOTBaseModel):
    @classmethod
    def indexed_fields(cls):
        indexed_fields = {}

        # Handle regular fields
        for fieldname, field in cls.model_fields.items():
            if any(isinstance(m, str) and m.startswith("indexed") for m in field.metadata):
                indexed_fields[fieldname] = field.metadata

        # Handle computed fields
        for fieldname, field in cls.model_computed_fields.items():
            return_type = field.return_type
            if get_origin(return_type) is Annotated:
                type_args = get_args(return_type)
                metadata = list(type_args[1:])  # Skip the first arg (the actual type)
                if any(isinstance(m, str) and m.startswith("indexed") for m in metadata):
                    indexed_fields[fieldname] = metadata

        return indexed_fields

    def model_dump(self, *args, mode="json", exclude_none=True, **kwargs):
        return _sanitize_mongo_operators(super().model_dump(*args, mode=mode, exclude_none=exclude_none, **kwargs))

    def sha1(self, data: str) -> str:
        return sha1(data.encode()).hexdigest()
