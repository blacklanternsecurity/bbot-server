from bbot_server.applets._base import BaseApplet


class Stats(BaseApplet):
    name = "Stats"
    description = "track global stats over time (e.g. number of assets, number of findings, etc.)"
    route_prefix = ""
