import json
import logging
import uuid as uuid_pkg
from datetime import datetime
from typing import List, Optional
from typing_extensions import Annotated
from pydantic.functional_validators import AfterValidator
from pydantic import ConfigDict, field_validator, ValidationInfo, BaseModel
from sqlmodel import inspect, Column, Field, SQLModel, JSON, Enum, Boolean, String, DateTime as SQLADateTime


log = logging.getLogger("bbot_server.models")


def naive_datetime_validator(d: datetime):
    """
    Converts all dates into UTC, then drops timezone information.

    This is needed to prevent inconsistencies in sqlite, because it is timezone-naive.
    """
    # drop timezone info
    return d.replace(tzinfo=None)


NaiveUTC = Annotated[datetime, AfterValidator(naive_datetime_validator)]


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        # handle datetime
        if isinstance(obj, datetime):
            return obj.isoformat()
        # handle uuid
        elif isinstance(obj, uuid_pkg.UUID):
            return str(obj)
        return super().default(obj)


class BBOTBaseModel(SQLModel):
    model_config = ConfigDict(extra="ignore")

    def __init__(self, *args, **kwargs):
        self._validated = None
        super().__init__(*args, **kwargs)

    @property
    def validated(self):
        try:
            if self._validated is None:
                self._validated = self.__class__.model_validate(self)
            return self._validated
        except AttributeError:
            return self

    def to_json(self, **kwargs):
        return json.dumps(self.validated.model_dump(), sort_keys=True, cls=CustomJSONEncoder, **kwargs)

    @classmethod
    def _pk_column_names(cls):
        return [column.name for column in inspect(cls).primary_key]

    def __hash__(self):
        return hash(self.to_json())

    def __eq__(self, other):
        return hash(self) == hash(other)


### EVENT ###


class Event(BBOTBaseModel, table=True):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        data = self._get_data(self.data, self.type)
        self.data = {self.type: data}
        if self.host:
            self.reverse_host = self.host[::-1]

    def get_data(self):
        return self._get_data(self.data, self.type)

    @staticmethod
    def _get_data(data, type):
        # handle SIEM-friendly format
        if isinstance(data, dict) and list(data) == [type]:
            return data[type]
        return data

    uuid: uuid_pkg.UUID = Field(
        default_factory=uuid_pkg.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    id: str = Field(index=True)
    type: str = Field(index=True)
    scope_description: str
    data: dict = Field(sa_type=JSON)
    host: Optional[str]
    port: Optional[int]
    netloc: Optional[str]
    # store the host in reversed form for efficient lookups by domain
    reverse_host: Optional[str] = Field(default="", exclude=True, index=True)
    resolved_hosts: List = Field(default=[], sa_type=JSON)
    dns_children: dict = Field(default={}, sa_type=JSON)
    web_spider_distance: int = 10
    scope_distance: int = Field(default=10, index=True)
    scan: str = Field(index=True)
    timestamp: NaiveUTC = Field(index=True)
    parent: str = Field(index=True)
    tags: List = Field(default=[], sa_type=JSON)
    module: str = Field(index=True)
    module_sequence: str
    discovery_context: str = ""
    discovery_path: List[str] = Field(default=[], sa_type=JSON)
    parent_chain: List[str] = Field(default=[], sa_type=JSON)


### ASSET ###


class AssetBase(BBOTBaseModel):

    class HistoryEntry(BaseModel):
        timestamp: NaiveUTC
        description: str

    def add_history_entry(self, event, description):
        self.history.append(self.HistoryEntry(timestamp=event.timestamp, description=description))

    host: str = Field(index=True, description="The hostname/IP address of the asset", primary_key=True)
    type: str = Field(
        description="The type of asset (DNS_NAME, IP_ADDRESS, or IP_RANGE)",
        sa_column=Column(Enum("DNS_NAME", "IP_ADDRESS", "IP_RANGE"), nullable=False, index=True),
    )
    first_seen: NaiveUTC = Field(index=True, description="The date and time when the asset was first observed")
    last_seen: NaiveUTC = Field(index=True, description="The most recent date and time when the asset was observed")

    # manual overrides
    custom_status: Optional[str] = Field(index=True, description="Custom override for the asset status")
    custom_risk_rating: Optional[int] = Field(
        default=None, ge=0, le=10, description="Custom risk rating assigned to the asset (must be between 0 and 10)"
    )
    custom_vuln_count: Optional[int] = Field(
        default=0,
        description="Number of custom (non-BBOT) vulnerabilities. These are added to the BBOT vuln count to get the total.",
    )
    custom_tags: List[str] = Field(
        default=[], sa_type=JSON, description="Custom set of tags associated with the asset"
    )
    confirmed: bool = Field(default=False, description="Whether the asset has been manually confirmed")
    ignored: bool = Field(default=False, description="Whether the asset has been manually ignored")
    notes_public: Optional[str] = Field(default="", description="Public notes about the asset")
    notes_private: Optional[str] = Field(default="", description="Private notes about the asset")
    history: List[HistoryEntry] = Field(
        default=[], sa_type=JSON, description="Historical data or changes related to the asset"
    )

    @field_validator("ignored")
    @classmethod
    def confirmed_and_ignored_mutually_exclusive(cls, v: bool, info: ValidationInfo) -> bool:
        if v and info.data.get("confirmed"):
            raise ValueError("An asset cannot be both confirmed and ignored")
        return v

    @field_validator("confirmed")
    @classmethod
    def ignored_and_confirmed_mutually_exclusive(cls, v: bool, info: ValidationInfo) -> bool:
        if v and info.data.get("ignored"):
            raise ValueError("An asset cannot be both ignored and confirmed")
        return v


class AssetModel(AssetBase, table=True):
    pass


class AssetOutput(AssetBase):
    open_ports: Optional[List[int]] = Field(default=[], sa_column=None, description="List of open ports on the asset")
    web_screenshots: Optional[List[str]] = Field(
        default=[], sa_column=None, description="List of web screenshot UUIDs"
    )
    technologies: Optional[List[str]] = Field(
        default=[], sa_column=None, description="List of technologies detected on the asset"
    )
    temptation: Optional[int] = Field(
        default=0,
        ge=0,
        le=10,
        sa_column=None,
        description='How "juicy" or "tempting" the asset is to an attacker (must be between 0 and 10)',
    )

    def absorb_event(self, event: Event):
        absorb_method = getattr(self, f"absorb_{event.type}", None)
        if absorb_method is not None and callable(absorb_method):
            absorb_method(event)

    def absorb_OPEN_TCP_PORT(self, event: Event):
        if event.port and event.port not in self.open_ports:
            self.open_ports.append(event.port)
            self.open_ports.sort()
            self.add_history_entry(event, f"New open port detected: {event.port}")

    def absorb_TECHNOLOGY(self, event: Event):
        if event.data["technology"] not in self.technologies:
            self.technologies.append(event.data["technology"])
            self.add_history_entry(event, f"New technology detected: {event.data['technology']}")


### SCAN ###


class ScanBase(BBOTBaseModel):
    id: str = Field(primary_key=True)
    name: str
    status: str
    started_at: NaiveUTC = Field(index=True)
    finished_at: Optional[NaiveUTC] = Field(default=None, sa_column=Column(SQLADateTime, nullable=True, index=True))
    duration_seconds: Optional[float] = Field(default=None)
    duration: Optional[str] = Field(default=None)
    target: dict = Field(sa_type=JSON)
    preset: dict = Field(sa_type=JSON)


class ScanModel(ScanBase, table=True):
    pass


class ScanOutput(ScanBase):
    last_contact: Optional[NaiveUTC]


### TARGET ###


class Target(BBOTBaseModel, table=True):
    name: str = "Default Target"
    strict_scope: bool = False
    seeds: List = Field(default=[], sa_type=JSON)
    whitelist: List = Field(default=None, sa_type=JSON)
    blacklist: List = Field(default=[], sa_type=JSON)
    hash: str = Field(sa_column=Column("hash", String, unique=True, primary_key=True, index=True))
    scope_hash: str = Field(sa_column=Column("scope_hash", String, index=True))
    seed_hash: str = Field(sa_column=Column("seed_hashhash", String, index=True))
    whitelist_hash: str = Field(sa_column=Column("whitelist_hash", String, index=True))
    blacklist_hash: str = Field(sa_column=Column("blacklist_hash", String, index=True))
    # only one target can be the default
    is_default: bool = Field(sa_column=Column("is_default", Boolean, unique=True, nullable=False))
