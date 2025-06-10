from typing import Annotated

from bbot_server.assets import Asset, CustomAssetFields
from bbot_server.applets.base import BaseApplet, api_endpoint
from bbot_server.modules.activity.activity_models import Activity


# add one field: 'cloud_providers' to the main asset model
class CloudFields(CustomAssetFields):
    cloud_providers: Annotated[list[str], "indexed"] = []


class CloudApplet(BaseApplet):
    name = "Cloud"
    watched_activities = ["NEW_DNS_LINK", "DNS_LINK_REMOVED"]
    description = "Cloud providers discovered during scans. Makes use of the cloudcheck library (https://github.com/blacklanternsecurity/cloudcheck)"
    attach_to = "root_applet"

    async def setup(self):
        import cloudcheck

        self._cloudcheck = cloudcheck
        return True, ""

    @api_endpoint(
        "/list/{host}",
        methods=["GET"],
        summary="List the cloud providers for a given asset (includes child DNS records)",
        mcp=True,
    )
    async def get_cloud_providers_for_asset(self, host: str) -> list[dict[str, str]]:
        # courteously, we trigger an update of the asset's cloud providers.
        cloud_providers, detail, activities = await self._refresh_cloud_providers(host)
        for activity in activities:
            await self.emit_activity(activity)
        if activities:
            await self.root._update_asset(host, {"cloud_providers": cloud_providers})
        return detail

    @api_endpoint(
        "/check/{host}",
        methods=["GET"],
        summary="Check a hostname or IP address against the cloud provider database",
    )
    async def cloudcheck(self, host: str) -> list[dict[str, str]]:
        # update the cloudcheck database
        await self._cloudcheck.update(cache_hrs=24)
        result = []
        for provider, provider_type, parent in self._cloudcheck.check(host):
            result.append({"provider": provider, "provider_type": provider_type, "belongs_to": str(parent)})
        return result

    @api_endpoint("/stats", methods=["GET"], summary="Statistics about cloud providers", mcp=True)
    async def cloud_providers_stats(
        self,
        domain: str = None,
        target_id: str = None,
    ) -> dict[str, int]:
        stats = {}
        domain = domain or None
        async for asset in self.root._get_assets(domain=domain, target_id=target_id, fields=["cloud_providers"]):
            cloud_providers = asset.get("cloud_providers", [])
            for provider in cloud_providers:
                try:
                    stats[provider] += 1
                except KeyError:
                    stats[provider] = 1
        # sort by number of assets, descending
        stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)
        return dict(stats)

    async def handle_activity(self, activity, asset):
        """
        Whenever a new DNS link is discovered, we re-evaluate the asset's cloud providers
        """
        _, _, activities = await self._refresh_cloud_providers(activity.host, activity, asset)
        return activities

    async def compute_stats(self, asset, statistics):
        cloud_providers = getattr(asset, "cloud_providers", [])
        cloud_providers_stats = statistics.get("cloud_providers", {})
        for provider in cloud_providers:
            try:
                cloud_providers_stats[provider] += 1
            except KeyError:
                cloud_providers_stats[provider] = 1
        cloud_providers_stats = dict(sorted(cloud_providers_stats.items(), key=lambda x: x[1], reverse=True))
        statistics["cloud_providers"] = cloud_providers_stats

    async def _refresh_cloud_providers(self, host: str, parent_activity: Activity = None, asset: Asset = None):
        """
        Given a host and its associated asset, update its cloud providers.

        Return the full details of the cloud provider results.
        """
        if not host:
            self.log.error(f"No host provided to _refresh_cloud_providers")
            return []

        if not asset:
            return []

        activities = []
        dns_links = asset.dns_links or {}

        old_cloud_providers = set(asset.cloud_providers or [])
        cloud_providers_detail = await self._dns_links_to_cloud_providers(host, dns_links)
        new_cloud_providers = {detail["provider"] for detail in cloud_providers_detail}

        cloud_providers_added = new_cloud_providers - old_cloud_providers
        cloud_providers_removed = old_cloud_providers - new_cloud_providers

        if cloud_providers_added or cloud_providers_removed:
            cloud_providers_added = sorted(cloud_providers_added)
            cloud_providers_removed = sorted(cloud_providers_removed)
            description = f"Change in cloud providers on [bold]{host}[/bold]: "
            if cloud_providers_added:
                description += f"Added [[COLOR]{','.join(cloud_providers_added)}[/COLOR]]"
                if cloud_providers_removed:
                    description += ", "
            if cloud_providers_removed:
                description += f"Removed [[COLOR]{','.join(cloud_providers_removed)}[/COLOR]]"

            activity = self.make_activity(
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
            activities.append(activity)

            asset.cloud_providers = sorted(new_cloud_providers)

        return sorted(new_cloud_providers), cloud_providers_detail, activities

    async def _dns_links_to_cloud_providers(self, host, dns_links: dict[str, list[str]]) -> list[dict[str, str]]:
        """
        Given a host and its DNS links, return all the cloud providers associated with the host.
        """
        results = []
        to_check = {("SELF", host)}
        for rdtype, records in dns_links.items():
            for record in records:
                if rdtype in ("A", "AAAA", "CNAME"):
                    to_check.add((rdtype, record))
        for rdtype, record in to_check:
            try:
                cloudcheck_results = await self.cloudcheck(record)
            except Exception as e:
                self.log.error(f'Error checking host "{record}" (type: {type(record)}) for cloud providers: {e}')
                import traceback

                self.log.error(traceback.format_stack())
                continue
            for result in cloudcheck_results:
                results.append(
                    {
                        "record": record,
                        "rdtype": rdtype,
                        "provider": result["provider"],
                        "provider_type": result["provider_type"],
                        "belongs_to": result["belongs_to"],
                    }
                )
        return results
