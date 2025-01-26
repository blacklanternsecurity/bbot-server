from bbot.models.pydantic import Event
from bbot_server.models.assets import Asset, AssetActivity
from bbot_server.applets._base import BaseApplet, api_endpoint


class Emails(BaseApplet):
    watched_events = ["EMAIL_ADDRESS"]
    description = "emails discovered during scans"
    route_prefix = ""

    async def ingest_event(self, asset: Asset, event: Event) -> list[AssetActivity]:
        activities = []
        email = event.data
        current_emails = self._get_emails(asset)
        if email not in current_emails:
            description = f"New email: [{email}]"
            description_colored = f"New email: [[dark_orange]{email}[/dark_orange]]"
            current_emails.add(email)
            current_emails = sorted(current_emails)
            email_activity = AssetActivity.create(
                type="NEW_EMAIL",
                asset=asset,
                event=event,
                fieldname="emails",
                value=current_emails,
                description=description,
                description_colored=description_colored,
            )
            activities.append(email_activity)
        return activities

    def _get_emails(self, asset: Asset) -> set[str]:
        return set(asset.fields.get("emails", [])) or set()

    @api_endpoint("/emails/{domain}", methods=["GET"], summary="Get emails by domain")
    async def get_emails(self, domain: str) -> list[str]:
        matching_assets = await self.root.assets.get_assets_by_host(domain)
        emails = set()
        for asset in matching_assets:
            emails.update(asset.fields.get("emails", []))
        return sorted(emails)
