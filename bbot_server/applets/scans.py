from bbot_server.models import Scan
from bbot_server.applets._base import BaseApplet, api_endpoint


class Scans(BaseApplet):

    data_model = Scan

    async def put_scan(self, scan: Scan):
        return await self.db.insert_or_update(scan)

    @api_endpoint("/", methods=["GET"], summary="Get Scans")
    async def get_scans(self) -> list[Scan]:
        return await self.db.find_many()
