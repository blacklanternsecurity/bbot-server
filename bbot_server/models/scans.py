from typing import Any, Union
from datetime import datetime

from bbot_server.models import BaseBBOTServerModel


class Scan(BaseBBOTServerModel):
    __tablename__ = "scans"

    name: str
    target: list[str] = []
    whitelist: list[str] = []
    blacklist: list[str] = []
    preset: dict[str, Any] = {}

    def make_preset(self):
        from bbot import Preset

        preset = Preset(**self.preset)
        target_preset = Preset(*self.target, whitelist=self.whitelist, blacklist=self.blacklist, scan_name=self.name)
        preset.merge(target_preset)
        return preset


class ScanRun(BaseBBOTServerModel):
    __tablename__ = "scan_runs"

    id: str
    name: str
    status: str
    target: dict[str, Any]
    preset: dict[str, Any]
    started_at: datetime
    finished_at: Union[datetime, None] = None
    duration_seconds: Union[float, None] = None
    duration: Union[str, None] = None
