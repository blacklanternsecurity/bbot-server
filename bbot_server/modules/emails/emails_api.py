# from bbot_server.workers.emails import EmailWorker
from bbot_server.applets.base import BaseApplet, api_endpoint, BaseModel, Field


class EmailsApplet(BaseApplet):
    name = "Emails"
    description = "emails discovered during scans"
    # watched_events = ["EMAIL_ADDRESS"]
    route_prefix = ""
    # workers = [EmailWorker]
    attach_to = "assets"

    class AssetFields(BaseModel):
        emails: list[str] = Field(default_factory=list)

    @api_endpoint("/emails/{domain}", methods=["GET"], summary="Get emails by domain", mcp=True)
    async def get_emails(self, domain: str) -> list[str]:
        emails = set()
        async for asset in self.root.assets.list_assets(domain=domain):
            emails.update(asset.emails)
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
