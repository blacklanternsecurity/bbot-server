from bbot.models.pydantic import BBOTBaseModel

_index_keywords = ["indexed", "indexed_text"]


class BaseBBOTServerModel(BBOTBaseModel):
    @classmethod
    def indexed_fields(cls):
        indexed_fields = {}
        for fieldname, field in cls.model_fields.items():
            for keyword in _index_keywords:
                if keyword in field.metadata:
                    indexed_fields[fieldname] = keyword
        return indexed_fields

    def model_dump(self, *args, mode="json", **kwargs):
        return super().model_dump(*args, mode=mode, **kwargs)
