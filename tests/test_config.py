import os
from tempfile import NamedTemporaryFile
from tests.conftest import TEST_CONFIG_PATH
from bbot_server.config import BBOT_SERVER_CONFIG as bbcfg


def test_config():
    os.environ["BBOT_SERVER_URL"] = "http://asdf:8000"
    bbcfg.refresh()
    assert bbcfg.url == "http://asdf:8000"
    assert bbcfg.event_store.uri == "mongodb://localhost:27017/test_bbot_server_events"

    os.environ["BBOT_SERVER_URL"] = "http://fdsa:8000"
    bbcfg.refresh()
    assert bbcfg.url == "http://fdsa:8000"
    assert bbcfg.event_store.uri == "mongodb://localhost:27017/test_bbot_server_events"

    tmp_config_file = NamedTemporaryFile(suffix=".yml")
    with open(tmp_config_file.name, "w") as f:
        f.write("""
url: http://qwer:8000
asset_store:
  uri: mongodb://localhost:27017/asdf
""")
    bbcfg.refresh(config_path=tmp_config_file.name)

    # should still be fdsa because of the env var, which takes precedence
    assert bbcfg.url == "http://fdsa:8000"
    # asset store uri should be overridden
    assert bbcfg.asset_store.uri == "mongodb://localhost:27017/asdf"
    # others should be untouched
    assert bbcfg.event_store.uri == "mongodb://localhost:27017/bbot_eventstore"

    # everything should be the same after a refresh
    bbcfg.refresh()
    assert bbcfg.url == "http://fdsa:8000"
    assert bbcfg.asset_store.uri == "mongodb://localhost:27017/asdf"
    assert bbcfg.event_store.uri == "mongodb://localhost:27017/bbot_eventstore"

    # reset back to testing defaults
    bbcfg.refresh(config_path=TEST_CONFIG_PATH)
    assert bbcfg.event_store.uri == "mongodb://localhost:27017/test_bbot_server_events"
