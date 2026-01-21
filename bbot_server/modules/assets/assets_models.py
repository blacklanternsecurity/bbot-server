from typing import Annotated

from bbot.models.pydantic import BBOTBaseModel
from fastapi import Body

from bbot_server.models.base import BaseRequestBody, QueryRequestBody


class BaseAssetRequestBody(BBOTBaseModel):
    host: Annotated[str, Body(description="Filter assets by host (exact match only)")] = None
    domain: Annotated[str, Body(description="Filter assets by domain (subdomains allowed)")] = None
    type: Annotated[str, Body(description="Filter assets by type (Asset, Technology, Vulnerability, etc.)")] = "Asset"
    target_id: Annotated[str, Body(description="Filter assets by target ID")] = None
    archived: Annotated[bool, Body(description="Whether to include archived assets")] = False
    active: Annotated[bool, Body(description="Whether to include active assets")] = True
    ignored: Annotated[bool, Body(description="Filter on whether the asset is ignored")] = False


class QueryAssetsRequestModel(BaseAssetRequestBody, QueryRequestBody):
    pass


class CountAssetsRequestBody(BaseAssetRequestBody, BaseRequestBody):
    pass
