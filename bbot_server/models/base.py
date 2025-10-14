import logging
from hashlib import sha1

from bbot.models.pydantic import BBOTBaseModel
from bbot_server.utils.misc import _sanitize_mongo_query

log = logging.getLogger("bbot_server.models")


class BaseBBOTServerModel(BBOTBaseModel):
    def model_dump(self, *args, mode="json", exclude_none=True, **kwargs):
        return _sanitize_mongo_query(super().model_dump(*args, mode=mode, exclude_none=exclude_none, **kwargs))

    def sha1(self, data: str) -> str:
        return sha1(data.encode()).hexdigest()
