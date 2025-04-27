import logging

from bbot.models.pydantic import BBOTBaseModel

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
        return super().model_dump(*args, mode=mode, exclude_none=exclude_none, **kwargs)
