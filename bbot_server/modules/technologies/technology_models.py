from pydantic import Field, computed_field
from typing import Annotated

from bbot_server.utils.misc import utc_now
from bbot_server.models.asset_models import BaseAssetFacet
from bbot_server.models.base import BaseRequestBody, CommonFilterFields, IgnoredFilterField, QueryRequestBody


class BaseTechnologiesRequestBody(CommonFilterFields, IgnoredFilterField):
    """Base request body for technology query/count endpoints."""

    technology: str | None = Field(None, description="Filter by technology name")


class QueryTechnologiesRequestBody(BaseTechnologiesRequestBody, QueryRequestBody):
    pass


class CountTechnologiesRequestBody(BaseTechnologiesRequestBody, BaseRequestBody):
    pass


class Technology(BaseAssetFacet):
    technology: Annotated[str, "indexed", "indexed-text"]
    last_seen: Annotated[float, "indexed"] = Field(default_factory=utc_now)

    @computed_field
    @property
    def id(self) -> Annotated[str, "indexed", "unique"]:
        """We dedupe technologies by technology+netloc"""
        return self.sha1(f"{self.technology}:{self.netloc}")
