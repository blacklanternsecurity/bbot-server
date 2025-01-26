from bbot_server.models.scans import Scan
from bbot_server.applets._base import BaseApplet, api_endpoint


async def bbot_scan(preset, output_url="http://localhost:8807/v1/events/"):
    from bbot import Preset

    main_preset = Preset.from_dict(preset)
    output_preset = Preset.from_dict(
        {
            "output_modules": [
                "http",
            ],
            "config": {
                "modules": {
                    "http": {
                        "url": output_url,
                    }
                }
            },
        }
    )
    main_preset.merge(output_preset)

    print(main_preset.to_dict())

    from bbot import Scanner

    scan = Scanner(preset=main_preset)
    await scan.async_start_without_generator()


class Scans(BaseApplet):
    description = "scans"
    include_apps = ["Scan_Runs"]
    _data_model = Scan

    @api_endpoint("/", methods=["GET"], summary="List scans")
    async def get_scans(self) -> list[Scan]:
        cursor = self.collection.find()
        scans = await cursor.to_list(length=None)
        scans = [Scan(**scan) for scan in scans]
        return scans

    @api_endpoint("/{name}", methods=["GET"], summary="Get a single target")
    async def get_scan(self, name: str) -> Scan:
        scan = await self.collection.find_one({"name": name})
        if scan is None:
            return
        return Scan(**scan)

    @api_endpoint("/", methods=["POST"], summary="Create a new scan")
    async def create_scan(self, scan: Scan) -> Scan:
        await self.collection.insert_one(scan.model_dump())
        return scan

    @api_endpoint("/{name}", methods=["DELETE"], summary="Delete a scan")
    async def delete_scan(self, name: str) -> None:
        await self.collection.delete_one({"name": name})

    @api_endpoint("/start/{name}", methods=["POST"], summary="Start a scan")
    async def start_scan(self, name: str) -> None:
        scan = await self.get_scan(name)
        if scan is None:
            return
        preset = scan.make_preset()
        baked_preset = preset.bake()

        # from multiprocessing import Process
        # bbot_scan_process = Process(target=bbot_scan, args=(preset.to_dict(),))
        # bbot_scan_process.daemon = False
        # bbot_scan_process.start()
        # bbot_scan_process.join(timeout=0)
        await bbot_scan(baked_preset.to_dict(include_target=True))
