import logging
from hashlib import sha1
from typing import Union

from bbot.models.pydantic import BBOTBaseModel
from bbot_server.errors import BBOTServerValueError
from bbot_server.utils.misc import _sanitize_mongo_query

log = logging.getLogger("bbot_server.models")


class BaseBBOTServerModel(BBOTBaseModel):
    def model_dump(self, *args, mode="json", exclude_none=True, **kwargs):
        return _sanitize_mongo_query(super().model_dump(*args, mode=mode, exclude_none=exclude_none, **kwargs))

    def sha1(self, data: str) -> str:
        return sha1(data.encode()).hexdigest()


class BaseScore:
    """Base class for mapping string levels to numeric scores."""

    levels: dict = {}
    name: str = "score"

    @classmethod
    def to_score(cls, value: Union[str, int]) -> int:
        """Convert a level to its numeric score."""
        if isinstance(value, int):
            if value not in cls.levels.values():
                raise BBOTServerValueError(f'Invalid {cls.name} score: "{value}". Must be between 1 and 5.')
            return value
        if isinstance(value, str):
            value = value.upper()
            if value not in cls.levels:
                raise BBOTServerValueError(
                    f'Invalid {cls.name} string: "{value}". Must be one of {list(cls.levels.keys())}'
                )
            return cls.levels[value]

    @classmethod
    def to_str(cls, score: int) -> str:
        """Convert a numeric score to its string equivalent."""
        for level, value in cls.levels.items():
            if value == score:
                return level
        raise BBOTServerValueError(f"Invalid {cls.name} score: {score}. Must be between 1 and 5.")
