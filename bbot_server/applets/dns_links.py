from bbot.models.pydantic import Event
from bbot_server.applets._base import BaseApplet
from bbot_server.asset_store.asset import Asset, AssetActivity


class DNS_Links(BaseApplet):
    watched_events = ["DNS_NAME"]
    description = "DNS Links"

    async def ingest_event(self, asset: Asset, event: Event) -> list[AssetActivity]:
        activities = []
        if event.type == "DNS_NAME":
            old_dns_records = asset.extra_fields.get("dns_records", {}) or {}
            old_dns_records_flattened = self._flatten_dns_records(old_dns_records)
            new_dns_records = getattr(event, "dns_children", {}) or {}
            new_dns_records_flattened = self._flatten_dns_records(new_dns_records)
            removed_dns_records = old_dns_records_flattened - new_dns_records_flattened
            added_dns_records = new_dns_records_flattened - old_dns_records_flattened

            asset.extra_fields["dns_records"] = new_dns_records

            for rdtype, record in removed_dns_records:
                description = f"DNS link removed: {event.host} -({rdtype})-> [{record}]"
                description_colored = f"DNS link removed: {event.host} -({rdtype})-> [[orange1]{record}[/orange1]]"
                dns_record_activity = AssetActivity(
                    type="DELETED_DNS_LINK",
                    event=event,
                    description=description,
                    description_colored=description_colored,
                )
                activities.append(dns_record_activity)

            for rdtype, record in added_dns_records:
                description = f"New DNS link: {event.host} -({rdtype})-> [{record}]"
                description_colored = f"New DNS link: {event.host} -({rdtype})-> [[orange1]{record}[/orange1]]"
                dns_record_activity = AssetActivity(
                    type="NEW_DNS_LINK",
                    event=event,
                    description=description,
                    description_colored=description_colored,
                )
                activities.append(dns_record_activity)

        return activities

    def _flatten_dns_records(self, dns_records: dict) -> set[tuple[str, str]]:
        flattened_records = set()
        for rdtype, records in dns_records.items():
            for record in records:
                flattened_records.add((rdtype, record))
        return flattened_records
