from bbot_server.models.activity_models import BaseAssetFacet
from bbot_server.applets._base import BaseApplet, api_endpoint, Field


class CloudProviders(BaseAssetFacet):
    cloud_providers: list[str] = Field(default_factory=list)


class CloudApplet(BaseApplet):
    name = "Cloud"
    description = "cloud resources discovered during scans"

    model = CloudProviders

    @api_endpoint("/{domain}", methods=["GET"], summary="Get cloud providers by domain")
    async def get_cloud_providers(self, host: str) -> list[str]:
        cloud_providers = await self._get_obj(host)
        if cloud_providers is None:
            return []
        return cloud_providers.cloud_providers
