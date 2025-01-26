from bbot_server.models.scans import ScanRun
from bbot_server.models.assets import AssetActivity
from bbot_server.applets._base import BaseApplet, api_endpoint


class Scan_Runs(BaseApplet):
    watched_events = ["SCAN"]
    description = "individual scan runs"
    _route_prefix = "/runs"
    _data_model = ScanRun

    async def ingest_event(self, asset, event) -> list[AssetActivity]:
        scan_run = ScanRun(**event.data_json)
        activity_type = f"SCAN_{scan_run.status}"

        existing_scan_run = await self.collection.find_one({"id": scan_run.id})
        if existing_scan_run:
            description = (
                f'Scan [{scan_run.name}] status changed from {existing_scan_run["status"]} to {scan_run.status}'
            )
            description_colored = f'Scan [[dark_orange]{scan_run.name}[/dark_orange]] status changed from {existing_scan_run["status"]} to {scan_run.status}'
            await self.collection.update_one({"id": scan_run.id}, {"$set": scan_run.model_dump()})
        else:
            description = f"Scan [{scan_run.name}] started"
            description_colored = f"Scan [[dark_orange]{scan_run.name}[/dark_orange]] started"
            await self.collection.insert_one(scan_run.model_dump())

        scan_run_activity = AssetActivity(
            type=activity_type,
            event=event,
            description=description,
            description_colored=description_colored,
        )
        return [scan_run_activity]

    @api_endpoint("/", methods=["GET"], summary="List individual BBOT scan runs")
    async def get_scan_runs(self) -> list[dict]:
        cursor = self.collection.find()
        scan_runs = []
        for run in await cursor.to_list(length=None):
            scan_runs.append(ScanRun(**run))

        return scan_runs
