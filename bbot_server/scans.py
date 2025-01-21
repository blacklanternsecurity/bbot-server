from typing import Any, Union
from pydantic import BaseModel
from datetime import datetime


class Scan(BaseModel):
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


class ScanRun(BaseModel):
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
