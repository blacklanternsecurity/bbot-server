from sqlmodel import select

from bbot_server.models import ScanModel, ScanOutput
from bbot_server.applets._base import BaseApplet, api_endpoint


class Scans(BaseApplet):

    description = "scans executed by BBOT"
    data_model = ScanModel

    async def put_scan(self, scan: ScanModel):
        return await self.db.insert_or_update(scan)

    @api_endpoint("/{scan_id}", methods=["GET"], summary="Get scan")
    async def get_scan(self, scan_uuid: str) -> ScanOutput:
        """
        Get a scan by UUID.
        """
        statement = select(self.model).where(self.model.id == scan_uuid)
        return await self.db.find_one(statement)

    @api_endpoint("/", methods=["GET"], summary="Get scans")
    async def get_scans(self) -> list[ScanOutput]:
        """
        Get all scans.
        """
        return await self.db.find_many()
