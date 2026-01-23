from pydantic import Field

from bbot_server.models.base import BaseRequestBody, CommonFilterFields, IgnoredFilterField, QueryRequestBody


class BaseAssetRequestBody(CommonFilterFields, IgnoredFilterField):
    """Base request body for asset query/count endpoints."""

    type: str = Field("Asset", description="Filter by asset type")


class QueryAssetsRequestModel(BaseAssetRequestBody, QueryRequestBody):
    pass


class CountAssetsRequestBody(BaseAssetRequestBody, BaseRequestBody):
    pass
