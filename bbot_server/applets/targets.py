from bbot_server.targets import Target
from bbot_server.applets._base import BaseApplet, api_endpoint


class Targets(BaseApplet):
    description = "targets"
    _data_model = Target

    @api_endpoint("/", methods=["GET"], summary="List targets")
    async def get_targets(self) -> list[Target]:
        return [Target(name="Default Target", whitelist=["evilcorp.com", "1.2.3.4/24"])]

    @api_endpoint("/{name}", methods=["GET"], summary="Get a single target")
    async def get_target(self, name: str) -> Target:
        return Target(name=name, whitelist=[
            "evilcorp.com",
            "1.2.3.4/24"
        ])

    @api_endpoint("/", methods=["POST"], summary="Create a new target")
    async def create_target(self, target: Target) -> Target:
        return target
