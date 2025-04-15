from pydantic import Field
from typing import Annotated

from bbot_server.applets._base import BaseApplet
from bbot_server.assets.custom_fields import CustomAssetFields


class DNSLinks(CustomAssetFields):
    dns_links: Annotated[dict[str, list[str]], "indexed"] = Field(default_factory=dict)


class DNSLinksApplet(BaseApplet):
    """
    This applet tracks DNS links between assets, as enumerated by the .dns_children attribute on BBOT events.

    Note that DNS links are not the same as DNS records, since they are hosts extracted from DNS records.

    Raw DNS records are tracked in another applet.

    TODO: allow querying on DNS links
    """

    name = "DNS Links"
    watched_events = ["DNS_NAME"]
    description = "DNS Links"

    async def handle_event(self, event, asset):
        activities = []
        old_dns_links = asset.dns_links or {}
        old_dns_links_flattened = self._flatten_dns_links(old_dns_links)
        new_dns_links = getattr(event, "dns_children", {}) or {}
        new_dns_links_flattened = self._flatten_dns_links(new_dns_links)
        removed_dns_links = old_dns_links_flattened - new_dns_links_flattened
        added_dns_links = new_dns_links_flattened - old_dns_links_flattened

        # remove no longer existent DNS links
        for rdtype, record in removed_dns_links:
            description = f"DNS link removed: [bold]{event.host}[/bold] -({rdtype})-> [[COLOR]{record}[/COLOR]]"
            records = old_dns_links.get(rdtype, [])
            records.remove(record)
            if not records:
                del old_dns_links[rdtype]
            else:
                old_dns_links[rdtype] = sorted(records)
            dns_link_activity = self.make_activity(
                type="DELETED_DNS_LINK",
                event=event,
                description=description,
            )
            activities.append(dns_link_activity)

        # add new DNS links
        for rdtype, record in added_dns_links:
            description = f"New DNS link: [bold]{event.host}[/bold] -({rdtype})-> [[COLOR]{record}[/COLOR]]"
            records = old_dns_links.get(rdtype, [])
            records.append(record)
            old_dns_links[rdtype] = sorted(records)
            dns_link_activity = self.make_activity(
                type="NEW_DNS_LINK",
                event=event,
                description=description,
            )
            activities.append(dns_link_activity)

        asset.dns_links = new_dns_links

        return activities

    def _flatten_dns_links(self, dns_links: dict) -> set[tuple[str, str]]:
        flattened_links = set()
        for rdtype, links in dns_links.items():
            for link in links:
                flattened_links.add((rdtype, link))
        return flattened_links
