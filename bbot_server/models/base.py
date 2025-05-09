import logging
from hashlib import sha1
from bbot.models.pydantic import BBOTBaseModel
from bbot_server.utils.misc import _sanitize_mongo_operators

log = logging.getLogger("bbot_server.models")


class BaseBBOTServerModel(BBOTBaseModel):
    @classmethod
    def indexed_fields(cls):
        indexed_fields = {}
        for fieldname, field in cls.model_fields.items():
            if any(isinstance(m, str) and m.startswith("indexed") for m in field.metadata):
                indexed_fields[fieldname] = field.metadata
        return indexed_fields

    def model_dump(self, *args, mode="json", exclude_none=True, **kwargs):
        return _sanitize_mongo_operators(super().model_dump(*args, mode=mode, exclude_none=exclude_none, **kwargs))

    def sha1(self, data: str) -> str:
        return sha1(data.encode()).hexdigest()
