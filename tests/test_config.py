import os
from tempfile import NamedTemporaryFile
from tests.conftest import TEST_CONFIG_PATH
from bbot_server.config import BBOT_SERVER_CONFIG as bbcfg


def test_config():
    os.environ["BBOT_SERVER_URL"] = "http://asdf:8000"
    bbcfg.refresh()
    assert bbcfg.url == "http://asdf:8000"
    assert bbcfg.database.uri == "postgresql+asyncpg://bbot:bbot@localhost:5432/test_bbot_server"

    os.environ["BBOT_SERVER_URL"] = "http://fdsa:8000"
    bbcfg.refresh()
    assert bbcfg.url == "http://fdsa:8000"
    assert bbcfg.database.uri == "postgresql+asyncpg://bbot:bbot@localhost:5432/test_bbot_server"

    tmp_config_file = NamedTemporaryFile(suffix=".yml")
    with open(tmp_config_file.name, "w") as f:
        f.write("""
url: http://qwer:8000
database:
  uri: postgresql+asyncpg://localhost:5432/custom_db
""")
    bbcfg.refresh(config_path=tmp_config_file.name)

    # should still be fdsa because of the env var, which takes precedence
    assert bbcfg.url == "http://fdsa:8000"
    # database uri should be overridden
    assert bbcfg.database.uri == "postgresql+asyncpg://localhost:5432/custom_db"

    # everything should be the same after a refresh
    bbcfg.refresh()
    assert bbcfg.url == "http://fdsa:8000"
    assert bbcfg.database.uri == "postgresql+asyncpg://localhost:5432/custom_db"

    # reset back to testing defaults
    os.environ.pop("BBOT_SERVER_URL", None)
    bbcfg.refresh(config_path=TEST_CONFIG_PATH)
    assert bbcfg.url == "http://localhost:8807/v1/"
    assert bbcfg.database.uri == "postgresql+asyncpg://bbot:bbot@localhost:5432/test_bbot_server"
