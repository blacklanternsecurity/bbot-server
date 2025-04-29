from typing import Annotated

from bbot_server.models.activity_models import Activity
from bbot_server.assets.custom_fields import CustomAssetFields
from bbot_server.applets._base import BaseApplet, api_endpoint


# add one field: 'cloud_providers' to the main asset model
class CloudFields(CustomAssetFields):
    cloud_providers: Annotated[list[str], "indexed"] = []


class CloudApplet(BaseApplet):
    name = "Cloud"
    watched_activities = ["NEW_DNS_LINK", "DNS_LINK_REMOVED"]
    description = "Cloud providers discovered during scans. Makes use of the cloudcheck library (https://github.com/blacklanternsecurity/cloudcheck)"

    async def setup(self):
        import cloudcheck

        self._cloudcheck = cloudcheck

    @api_endpoint(
        "/list/{host}",
        methods=["GET"],
        summary="List the cloud providers for a given asset (includes child DNS records)",
    )
    async def get_cloud_providers_for_asset(self, host: str) -> list[dict[str, str]]:
        # courteously, we trigger an update of the asset's cloud providers.
        return await self._refresh_cloud_providers(host)

    @api_endpoint(
        "/check/{host}", methods=["GET"], summary="Check a hostname or IP address against the cloud provider database"
    )
    async def cloudcheck(self, host: str) -> list[dict[str, str]]:
        result = []
        for provider, provider_type, parent in self._cloudcheck.check(host):
            result.append({"provider": provider, "provider_type": provider_type, "belongs_to": str(parent)})
        return result

    async def handle_activity(self, activity):
        """
        Whenever a new DNS link is discovered, we re-evaluate the asset's cloud providers
        """
        await self._refresh_cloud_providers(activity.host, activity)

    async def compute_stats(self, asset, statistics):
        cloud_providers = getattr(asset, "cloud_providers", [])
        cloud_providers_stats = statistics.get("cloud_providers", {})
        for provider in cloud_providers:
            try:
                cloud_providers_stats[provider] += 1
            except KeyError:
                cloud_providers_stats[provider] = 1
        statistics["cloud_providers"] = cloud_providers_stats

    async def _refresh_cloud_providers(self, host: str, parent_activity: Activity = None):
        asset = await self.root._get_asset(host=host, fields=["dns_links", "cloud_providers"])
        if not asset:
            return []

        dns_links = asset.get("dns_links", {})

        old_cloud_providers = set(asset.get("cloud_providers", []))
        cloud_providers_detail = await self._dns_links_to_cloud_providers(host, dns_links)
        new_cloud_providers = {detail["provider"] for detail in cloud_providers_detail}

        cloud_providers_added = new_cloud_providers - old_cloud_providers
        cloud_providers_removed = old_cloud_providers - new_cloud_providers

        if cloud_providers_added or cloud_providers_removed:
            cloud_providers_added = sorted(cloud_providers_added)
            cloud_providers_removed = sorted(cloud_providers_removed)
            description = f"Cloud providers changed on [bold]{host}[/bold],"
            if cloud_providers_added:
                description += f" Added: [[COLOR]{','.join(cloud_providers_added)}[/COLOR]]"
            if cloud_providers_removed:
                description += f" Removed: [[COLOR]{','.join(cloud_providers_removed)}[/COLOR]]"
            await self.emit_activity(
                type="CLOUD_PROVIDER_CHANGE",
                host=host,
                description=description,
                parent_activity=parent_activity,
                detail={
                    "added": sorted(cloud_providers_added),
                    "removed": sorted(cloud_providers_removed),
                    "details": cloud_providers_detail,
                },
            )

            await self.root._update_asset(host, {"cloud_providers": sorted(new_cloud_providers)})

        return cloud_providers_detail

    async def _dns_links_to_cloud_providers(self, host, dns_links: dict[str, list[str]]) -> list[dict[str, str]]:
        # update the cloudcheck database
        await self._cloudcheck.update(cache_hrs=24)
        results = []
        to_check = {("SELF", host)}
        for rdtype, records in dns_links.items():
            for record in records:
                if rdtype in ("A", "AAAA", "CNAME"):
                    to_check.add((rdtype, record))
        for rdtype, record in to_check:
            for provider, provider_type, belongs_to in self._cloudcheck.check(record):
                results.append(
                    {
                        "record": record,
                        "rdtype": rdtype,
                        "provider": provider,
                        "provider_type": provider_type,
                        "belongs_to": belongs_to,
                    }
                )
        return results
