from bbot.models.pydantic import Event
from bbot_server.applets._base import BaseApplet, api_endpoint
from bbot_server.asset_store.asset import Asset, AssetActivity


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
            description_colored = f"New email: [[orange1]{email}[/orange1]]"
            current_emails.add(email)
            email_activity = AssetActivity(
                type="NEW_EMAIL", event=event, description=description, description_colored=description_colored
            )
            activities.append(email_activity)
            asset.extra_fields["emails"] = sorted(current_emails)
        return activities

    def _get_emails(self, asset: Asset) -> set[str]:
        return set(asset.extra_fields.get("emails", [])) or set()

    @api_endpoint("/emails", methods=["GET"], summary="Get all the emails")
    async def get_emails(self) -> list[str]:
        print("GETTING EMAILS")
