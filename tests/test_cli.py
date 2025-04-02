from pydantic import BaseModel
from typing import Union, List, Dict, Any

from bbot_server.cli.common import json_to_csv


def test_json_to_csv():
    json_data = [
        {"name": "test", "value": 1, "value2": [{"a": 2}]},
        {"name": "test2", "value": 2, "value2": {"a": [1, 2]}, "value3": "test"},
    ]
    csv_data = list(json_to_csv(json_data, fieldnames=["name", "value", "value2"]))
    assert csv_data == [
        b"name,value,value2\r\n",
        b'test,1,"[{""a"":2}]"\r\n',
        b'test2,2,"{""a"":[1,2]}"\r\n',
    ]

    # same exact thing but with pydantic model
    class TestModel(BaseModel):
        name: str = None
        value: int = None
        value2: List[Dict[str, Any]] = None
        value3: str = None

    pydantic_data = [
        TestModel(name="test", value=1, value2=[{"a": 2}]),
        TestModel(name="test2", value=2, value2=[{"a": [1, 2]}], value3="test"),
    ]

    csv_data_pydantic = list(json_to_csv(pydantic_data, fieldnames=["name", "value", "value2"]))
    assert csv_data_pydantic == [
        b"name,value,value2\r\n",
        b'test,1,"[{""a"":2}]"\r\n',
        b'test2,2,"[{""a"":[1,2]}]"\r\n',
    ]


def test_bbctl():
    import yaml
    import subprocess
    from pathlib import Path

    TEST_CONFIG_PATH = Path(__file__).parent / "test_config.yml"

    result = subprocess.run(["bbctl", "server", "current-config"], capture_output=True, text=True)
    assert result.returncode == 0
    config = yaml.safe_load(result.stdout)
    assert config["event_store"]["uri"] == "mongodb://localhost:27017/bbot_eventstore"

    result = subprocess.run(
        ["bbctl", "--config", str(TEST_CONFIG_PATH), "server", "current-config"], capture_output=True, text=True
    )
    assert result.returncode == 0
    config = yaml.safe_load(result.stdout)
    assert config["event_store"]["uri"] == "mongodb://localhost:27017/test_bbot_server_events"
