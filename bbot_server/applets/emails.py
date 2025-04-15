# from bbot_server.watchdogs.emails import EmailWatchdog
from bbot_server.applets._base import BaseApplet, api_endpoint, BaseModel, Field


class EmailsApplet(BaseApplet):
    name = "Emails"
    description = "emails discovered during scans"
    # watched_events = ["EMAIL_ADDRESS"]
    route_prefix = ""
    # watchdogs = [EmailWatchdog]

    class AssetFields(BaseModel):
        emails: list[str] = Field(default_factory=list)

    @api_endpoint("/emails/{domain}", methods=["GET"], summary="Get emails by domain")
    async def get_emails(self, domain: str) -> list[str]:
        matching_assets = await self.root.assets.get_assets_by_host(domain)
        emails = set()
        for asset in matching_assets:
            emails.update(asset.fields.get("emails", []))
        return sorted(emails)

    # async def handle_event(self, asset: Asset, event: Event) -> list[Activity]:
    #     activities = []
    #     email = event.data
    #     current_emails = set(asset.fields.get("emails", [])) or set()
    #     if email not in current_emails:
    #         description = f"New email: [{email}]"
    #         description_colored = f"New email: [[COLOR]{email}[/COLOR]]"
    #         current_emails.add(email)
    #         current_emails = sorted(current_emails)
    #         email_activity = Activity.create(
    #             type="NEW_EMAIL",
    #             asset=asset,
    #             event=event,
    #             fieldname="emails",
    #             value=current_emails,
    #             description=description,
    #             description_colored=description_colored,
    #         )
    #         activities.append(email_activity)
    #     return activities
