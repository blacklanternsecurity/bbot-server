from copy import deepcopy
from typing import Optional
from pydantic import BaseModel, Field

from bbot.models.pydantic import Event
from bbot_server.models.assets import Asset, AssetActivity
from bbot_server.applets._base import BaseApplet


class DNSLinksApplet(BaseApplet):
    name = "DNS Links"
    # watched_events = ["DNS_NAME"]
    description = "DNS Links"

    class AssetFields(BaseModel):
        dns_records: dict[str, list[str]] = Field(default_factory=dict)

    # async def handle_event(self, asset: Asset, event: Event) -> list[AssetActivity]:
    #     activities = []
    #     if event.type == "DNS_NAME":
    #         old_dns_records = asset.dns_records or {}
    #         old_dns_records_flattened = self._flatten_dns_records(old_dns_records)
    #         new_dns_records = getattr(event, "dns_children", {}) or {}
    #         new_dns_records_flattened = self._flatten_dns_records(new_dns_records)
    #         removed_dns_records = old_dns_records_flattened - new_dns_records_flattened
    #         added_dns_records = new_dns_records_flattened - old_dns_records_flattened

    #         # remove no longer existent DNS links
    #         for rdtype, record in removed_dns_records:
    #             description = f"DNS link removed: {event.host} -({rdtype})-> [{record}]"
    #             description_colored = (
    #                 f"DNS link removed: {event.host} -({rdtype})-> [[dark_orange]{record}[/dark_orange]]"
    #             )
    #             records = old_dns_records.get(rdtype, [])
    #             records.remove(record)
    #             if not records:
    #                 del old_dns_records[rdtype]
    #             else:
    #                 old_dns_records[rdtype] = sorted(records)
    #             dns_record_activity = AssetActivity.create(
    #                 type="DELETED_DNS_LINK",
    #                 asset=asset,
    #                 event=event,
    #                 fieldname="dns_records",
    #                 value=deepcopy(old_dns_records),
    #                 description=description,
    #                 description_colored=description_colored,
    #             )
    #             activities.append(dns_record_activity)

    #         # add new DNS links
    #         for rdtype, record in added_dns_records:
    #             description = f"New DNS link: {event.host} -({rdtype})-> [{record}]"
    #             description_colored = f"New DNS link: {event.host} -({rdtype})-> [[dark_orange]{record}[/dark_orange]]"
    #             records = old_dns_records.get(rdtype, [])
    #             records.append(record)
    #             old_dns_records[rdtype] = sorted(records)
    #             dns_record_activity = AssetActivity.create(
    #                 type="NEW_DNS_LINK",
    #                 asset=asset,
    #                 event=event,
    #                 fieldname="dns_records",
    #                 value=deepcopy(old_dns_records),
    #                 description=description,
    #                 description_colored=description_colored,
    #             )
    #             activities.append(dns_record_activity)

    #     return activities

    def _flatten_dns_records(self, dns_records: dict) -> set[tuple[str, str]]:
        flattened_records = set()
        for rdtype, records in dns_records.items():
            for record in records:
                flattened_records.add((rdtype, record))
        return flattened_records
