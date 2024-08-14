from bbot_io.models import Scan
from bbot_io.applets.base import BaseApplet, api_endpoint


class Scans(BaseApplet):

    model = Scan

    async def put_scan(self, scan: Scan):
        return await self.db.insert(scan)

    @api_endpoint("/", methods=["GET"], summary="Get Scans")
    async def get_scans(self) -> list[Scan]:
        return await self.db.find()
