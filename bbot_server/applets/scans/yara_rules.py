from bbot_server.applets._base import BaseApplet, api_endpoint


class YaraRulesApplet(BaseApplet):
    name = "YARA Rules"
    description = "add or remove custom YARA rules"

    @api_endpoint("/", methods=["GET"], summary="Get all YARA rules")
    async def get_yara_rules(self) -> list[str]:
        return []
