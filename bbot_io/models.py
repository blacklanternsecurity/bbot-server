import json
from datetime import datetime
from typing import List, Optional, Union
from pydantic import BaseModel, ConfigDict


class Event(BaseModel):
    type: str
    id: str
    scope_description: str
    data: Union[str, dict]
    host: Optional[str] = None
    resolved_hosts: List = []
    dns_children: dict = {}
    web_spider_distance: int = 10
    scope_distance: int = 10
    scan: str
    timestamp: datetime
    parent: str
    tags: List = []
    module: str
    module_sequence: str
    discovery_context: str = ""
    # discovery_path: List[str] = []

    model_config = ConfigDict(extra="ignore")

    _metadata: dict = {
        # these nested fields need to be serialized by relational databases
        "json_fields": ["resolved_hosts", "dns_children", "tags", "data"]
    }

    def model_dump(self, *args, **kwargs):
        event_dict = super().model_dump(*args, **kwargs)
        event_dict["timestamp"] = event_dict["timestamp"].timestamp()
        return event_dict

    @classmethod
    def from_flattened(cls, flattened):
        event_dict = dict(flattened)
        for field in cls._metadata.default["json_fields"]:
            if field in event_dict:
                event_dict[field] = json.loads(event_dict[field])
        return cls(**event_dict)

    def flatten(self):
        """
        Flatten the event by JSON-serializing nested attributes such as `resolved_hosts`

        This is useful for relational DBs like SQLite.
        """
        event_dict = self.model_dump(exclude_none=True)
        # event_dict["timestamp"] = event_dict["timestamp"].timestamp()
        for field in self._metadata["json_fields"]:
            if field in event_dict:
                event_dict[field] = json.dumps(event_dict[field])
        return event_dict

    def __hash__(self):
        return hash(json.dumps(self.model_dump(), sort_keys=True))
