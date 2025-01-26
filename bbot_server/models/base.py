from bbot.models.pydantic import BBOTBaseModel


class BaseBBOTServerModel(BBOTBaseModel):
    _type: str

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not getattr(self, "__tablename__", None):
            self._type = self.__class__.__name__
