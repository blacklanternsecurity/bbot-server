from bbot.models.pydantic import BBOTBaseModel

_index_keywords = ["indexed", "indexed_text"]


import logging

log = logging.getLogger("bbot_server.models")


class BaseBBOTServerModel(BBOTBaseModel):
    @classmethod
    def indexed_fields(cls):
        indexed_fields = {}
        for fieldname, field in cls.model_fields.items():
            for keyword in _index_keywords:
                if keyword in field.metadata:
                    indexed_fields[fieldname] = keyword
                    break
        return indexed_fields

    def model_dump(self, *args, mode="json", exclude_none=True, **kwargs):
        return super().model_dump(*args, mode=mode, exclude_none=exclude_none, **kwargs)
