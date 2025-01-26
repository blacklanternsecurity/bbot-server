import orjson

from bbot.models.pydantic import Event
from bbot_server.models.assets import Asset, AssetActivity
from bbot_server.applets._base import BaseApplet, api_endpoint


class Findings(BaseApplet):
    watched_events = ["VULNERABILITY", "FINDING"]
    description = "vulnerabilities discovered during scans"
    route_prefix = ""
    fieldnames = ["vulnerabilities", "findings"]

    async def ingest_event(self, asset: Asset, event: Event) -> list[AssetActivity]:
        activities = []
        vuln_id = event.id
        vuln_description = event.data_json["description"]
        if event.type == "VULNERABILITY":
            fieldname = "vulnerabilities"
        elif event.type == "FINDING":
            fieldname = "findings"
        current_vulns = set(asset.fields.get(fieldname, []))
        if vuln_id not in current_vulns:
            description = f"New {fieldname}: [{vuln_description}]"
            description_colored = f"New {fieldname}: [[dark_orange]{vuln_description}[/dark_orange]]"
            current_vulns.add(vuln_id)
            current_vulns = sorted(current_vulns)
            vuln_activity = AssetActivity.create(
                type=f"NEW_{event.type}",
                asset=asset,
                event=event,
                fieldname=fieldname,
                value=current_vulns,
                description=description,
                description_colored=description_colored,
            )
            activities.append(vuln_activity)
        return activities

    @api_endpoint("/{host}/findings", methods=["GET"], summary="Get all the findings for a host")
    async def get_findings(self, host: str) -> list[str]:
        asset = await self.root.assets.get(host)
        fields = getattr(asset, "fields", {})
        findings = fields.get("findings", [])
        return findings

    @api_endpoint("/{host}/vulnerabilities", methods=["GET"], summary="Get all the vulnerabilities for a host")
    async def get_vulnerabilities(self, host: str) -> list[str]:
        asset = await self.root.assets.get(host)
        fields = getattr(asset, "fields", {})
        vulns = fields.get("vulnerabilities", [])
        return vulns
