import json
import uuid as uuid_pkg
from datetime import datetime
from pydantic import ConfigDict
from typing import List, Optional
from typing_extensions import Annotated
from sqlalchemy.sql.schema import Column
from sqlmodel import Field, SQLModel, JSON
from pydantic.functional_validators import AfterValidator
from sqlalchemy import Boolean, String, DateTime as SQLADateTime


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
    uuid: uuid_pkg.UUID = Field(
        default_factory=uuid_pkg.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )

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

    def to_json(self):
        return json.dumps(self.validated.model_dump(), sort_keys=True, cls=CustomJSONEncoder)

    def __hash__(self):
        return hash(self.to_json())

    def __eq__(self, other):
        return hash(self) == hash(other)


class Event(BBOTBaseModel, table=True):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if isinstance(self.data, str):
            self.data = {self.type: self.data}
        if self.host:
            self.reverse_host = self.host[::-1]

    def get_data(self):
        # handle SIEM-friendly format
        if isinstance(self.data, dict) and list(self.data) == [self.type]:
            return self.data[self.type]
        return self.data

    id: str = Field(index=True)
    type: str
    scope_description: str
    data: dict = Field(sa_type=JSON)
    host: Optional[str] = Field(default=None, index=True)
    # store the host in reversed form for efficient lookups by domain
    reverse_host: Optional[str] = Field(default="", exclude=True, index=True)
    resolved_hosts: List = Field(default=[], sa_type=JSON)
    dns_children: dict = Field(default={}, sa_type=JSON)
    web_spider_distance: int = 10
    scope_distance: int = 10
    scope_description: str
    scan: str = Field(index=True)
    timestamp: NaiveUTC
    parent: str = Field(index=True)
    tags: List = Field(default=[], sa_type=JSON)
    module: str = Field(index=True)
    module_sequence: str
    discovery_context: str = ""
    discovery_path: List[str] = Field(default=[], sa_type=JSON)
    parent_chain: List[str] = Field(default=[], sa_type=JSON)


class Scan(BBOTBaseModel, table=True):
    uuid: Optional[uuid_pkg.UUID] = Field(default_factory=uuid_pkg.uuid4, index=True, nullable=False)
    id: str = Field(primary_key=True)
    name: str
    status: str
    started_at: NaiveUTC
    finished_at: Optional[NaiveUTC] = Field(default=None, sa_column=Column(SQLADateTime, nullable=True))
    duration_seconds: Optional[float] = Field(default=None)
    duration: Optional[str] = Field(default=None)
    target: dict = Field(sa_type=JSON)
    preset: dict = Field(sa_type=JSON)


class Target(BBOTBaseModel, table=True):
    uuid: Optional[uuid_pkg.UUID] = Field(default_factory=uuid_pkg.uuid4, index=True, nullable=False)
    name: str = "Default Target"
    strict_scope: bool = False
    seeds: List = Field(default=[], sa_type=JSON)
    whitelist: List = Field(default=None, sa_type=JSON)
    blacklist: List = Field(default=[], sa_type=JSON)
    hash: str = Field(sa_column=Column("hash", String, unique=True, primary_key=True, index=True))
    scope_hash: str
    seed_hash: str
    whitelist_hash: str
    blacklist_hash: str
    # only one target can be the default
    is_default: bool = Field(sa_column=Column("is_default", Boolean, unique=True))
