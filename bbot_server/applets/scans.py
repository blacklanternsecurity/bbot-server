from uuid import UUID
from sqlmodel import select

from bbot_server.models import Scan
from bbot_server.applets._base import BaseApplet, api_endpoint


class Scans(BaseApplet):

    data_model = Scan

    async def put_scan(self, scan: Scan):
        return await self.db.insert_or_update(scan)

    @api_endpoint("/{scan_uuid}", methods=["GET"], summary="Get scan")
    async def get_scan(self, scan_uuid: UUID) -> Scan:
        """
        Get a scan by UUID.
        """
        statement = select(self.model).where(self.model.uuid == scan_uuid)
        return await self.db.find_one(statement)

    @api_endpoint("/", methods=["GET"], summary="Get scans")
    async def get_scans(self) -> list[Scan]:
        """
        Get all scans.
        """
        return await self.db.find_many()
