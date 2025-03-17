from bbot_server.models.assets import Asset, AssetActivity
from bbot_server.applets._base import BaseApplet, api_endpoint, BaseModel, Field


class Risk(BaseApplet):
    name = "Risk"
    description = "basic risk scores for assets"
    route_prefix = ""

    @api_endpoint("/{host}/risk", methods=["GET"], summary="Get the risk rating for a host")
    async def get_risk(self, host: str) -> list[str]:
        """
        Returns the user-defined risk rating for a host.

        If not set, returns the highest risk rating based on the findings and vulnerabilities discovered for that asset.
        """
        return []

    @api_endpoint("/{host}/risk", methods=["POST"], summary="Set the risk rating for a host")
    async def set_risk(self, host: str, risk: str):
        """
        Sets the user-defined risk rating for a host.
        """
        pass
