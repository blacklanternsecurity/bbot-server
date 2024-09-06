import json
from datetime import datetime
from bbot_io.models import Event


def test_event_validation():
    event_json = {
        "type": "IP_ADDRESS",
        "id": "IP_ADDRESS:4b84b15bff6ee5796152495a230e45e3d7e947d9",
        "scope_description": "in-scope",
        "data": "127.0.0.1",
        "host": "127.0.0.1",
        "resolved_hosts": ["127.0.0.1"],
        "dns_children": {},
        "web_spider_distance": 0,
        "scope_distance": 0,
        "scan": "SCAN:5dbfad2e8d8f6f7c6817f996d1dc77373a6f9898",
        "timestamp": "2024-07-12T19:55:16.980804+00:00",
        "parent": "SCAN:5dbfad2e8d8f6f7c6817f996d1dc77373a6f9898",
        "tags": ["private-ip", "target", "ipv4", "in-scope"],
        "module": "TARGET",
        "module_sequence": "TARGET",
        "discovery_context": "Scan elden_tammy seeded with IP_ADDRESS: 127.0.0.1",
        "discovery_path": [
            [
                "IP_ADDRESS:4b84b15bff6ee5796152495a230e45e3d7e947d9",
                "Scan elden_tammy seeded with IP_ADDRESS: 127.0.0.1",
            ]
        ],
    }

    event = Event(**event_json)

    # data attribute should be automatically converted to dict
    assert event.data == {"IP_ADDRESS": "127.0.0.1"}
    # make sure timestamp behaves how we expect
    assert isinstance(event.timestamp, str)
    assert event.timestamp == "2024-07-12T19:55:16.980804+00:00"
    # it shouldn't get converted into a datetime object until .validate is called
    assert isinstance(event.validated.timestamp, datetime)
    assert event.validated.timestamp == datetime(2024, 7, 12, 19, 55, 16, 980804, tzinfo=None)

    # JSON-serialize and deserialize it, and make sure it's the same
    event_dict = event.model_dump()
    assert event_dict["data"] == {"IP_ADDRESS": "127.0.0.1"}
    assert event_dict["timestamp"] == "2024-07-12T19:55:16.980804+00:00"
    event_dict_validated = event.validated.model_dump()
    assert event_dict_validated["data"] == {"IP_ADDRESS": "127.0.0.1"}
    assert event_dict_validated["timestamp"] == datetime(2024, 7, 12, 19, 55, 16, 980804, tzinfo=None)

    event2_loaded_json = json.loads(event.to_json())
    assert event2_loaded_json["data"] == {"IP_ADDRESS": "127.0.0.1"}
    assert event2_loaded_json["timestamp"] == "2024-07-12T19:55:16.980804"

    event3_loaded_json = json.loads(event.validated.to_json())
    assert event3_loaded_json["data"] == {"IP_ADDRESS": "127.0.0.1"}
    assert event2_loaded_json["timestamp"] == "2024-07-12T19:55:16.980804"

    assert event3_loaded_json["data"] == event2_loaded_json["data"] == {"IP_ADDRESS": "127.0.0.1"}
    event2 = Event(**event2_loaded_json)
    assert event2.timestamp == "2024-07-12T19:55:16.980804"

    event3 = Event(**event3_loaded_json)
    assert event3.timestamp == "2024-07-12T19:55:16.980804"

    event2_json = event2.to_json()
    event3_json = event3.to_json()
    assert event3_json == event2_json
    # this doesn't match because the first one has a string for its data
    assert event2_json != event_json
    assert event3.data == event2.data == {"IP_ADDRESS": "127.0.0.1"}
    assert event2.data == event.data
    assert isinstance(event2.timestamp, str)
    assert isinstance(event2.validated.timestamp, datetime)
    assert isinstance(event3.timestamp, str)
    assert isinstance(event3.validated.timestamp, datetime)
    assert hash(event3) == hash(event2) == hash(event)
