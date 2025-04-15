from bbot_server.applets._base import BaseApplet, api_endpoint, BaseModel, Field


class FindingsApplet(BaseApplet):
    name = "Findings"
    # watched_events = ["VULNERABILITY", "FINDING"]
    description = "vulnerabilities discovered during scans"
    route_prefix = ""

    class AssetFields(BaseModel):
        vulnerabilities: list[str] = Field(default_factory=list)
        findings: list[str] = Field(default_factory=list)

    # async def handle_event(self, asset: Asset, event: Event) -> list[Activity]:
    #     activities = []
    #     vuln_id = event.id
    #     vuln_description = event.data_json["description"]
    #     if event.type == "VULNERABILITY":
    #         fieldname = "vulnerabilities"
    #     elif event.type == "FINDING":
    #         fieldname = "findings"
    #     current_vulns = set(asset.fields.get(fieldname, []))
    #     if vuln_id not in current_vulns:
    #         description = f"New {fieldname}: [{vuln_description}]"
    #         description_colored = f"New {fieldname}: [[COLOR]{vuln_description}[/COLOR]]"
    #         current_vulns.add(vuln_id)
    #         current_vulns = sorted(current_vulns)
    #         vuln_activity = Activity.create(
    #             type=f"NEW_{event.type}",
    #             asset=asset,
    #             event=event,
    #             fieldname=fieldname,
    #             value=current_vulns,
    #             description=description,
    #             description_colored=description_colored,
    #         )
    #         activities.append(vuln_activity)
    #     return activities

    @api_endpoint("/{host}/findings", methods=["GET"], summary="Get all the findings for a host")
    async def get_findings(self, host: str) -> list[str]:
        asset = await self.root.assets.get_asset(host)
        findings = asset.findings or []
        return findings

    @api_endpoint("/{host}/vulnerabilities", methods=["GET"], summary="Get all the vulnerabilities for a host")
    async def get_vulnerabilities(self, host: str) -> list[str]:
        asset = await self.root.assets.get(host)
        vulns = asset.vulns or []
        return vulns
