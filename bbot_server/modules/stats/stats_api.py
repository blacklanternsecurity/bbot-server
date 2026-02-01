from typing import Any

from bbot_server.assets import Asset
from bbot_server.modules.stats.stats_models import BBOTStats
from bbot_server.applets.base import BaseApplet, api_endpoint

"""
TODO:

Stats could be preregistered both with the hostname and every parent subdomain.
    That way, we can have counts/stats on hand for:
    - www.test.evilcorp.com
    - test.evilcorp.com
    - evilcorp.com
    The stats for evilcorp.com will encompass/summarize those for all its child hosts

Stats should also be compiled by scan.

Or, we could compute them on the fly. This might be easier, especially with something like metabase.
    We could cache API calls at the proxy layer to avoid overloading the database.
"""


class StatsApplet(BaseApplet):
    name = "Stats"
    description = "track global stats over time (e.g. number of assets, number of findings, etc.)"
    route_prefix = ""
    attach_to = "assets"
    model = BBOTStats

    @api_endpoint("/stats", methods=["GET"], summary="Get statistics for a given target or domain")
    async def get_stats(self, domain: str = None, host: str = None, target_id: str = None) -> dict[str, Any]:
        stats = {}
        async for asset in self.root.assets.mongo_iter(
            domain=domain,
            host=host,
            target_id=target_id,
        ):
            asset = Asset(**asset)
            for applet in self.root.all_child_applets(include_self=True):
                await applet.compute_stats(asset, stats)
        return stats
