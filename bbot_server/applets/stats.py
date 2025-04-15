from bbot_server.applets._base import BaseApplet


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


class Stats(BaseApplet):
    name = "Stats"
    description = "track global stats over time (e.g. number of assets, number of findings, etc.)"
    route_prefix = ""
