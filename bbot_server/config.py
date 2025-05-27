import os
import logging
from uuid import UUID
from pathlib import Path
from omegaconf import OmegaConf

log = logging.getLogger("bbot_server.config")


BBOT_SERVER_DIR = Path(__file__).parent
API_KEY_NAME = "X-API-Key"
VALID_API_KEYS = set()

# Load defaults
BBOT_SERVER_DEFAULTS_PATH = BBOT_SERVER_DIR / "defaults.yml"
BBOT_SERVER_DEFAULTS = OmegaConf.load(BBOT_SERVER_DEFAULTS_PATH)
BBOT_SERVER_CONFIG = BBOT_SERVER_DEFAULTS
BBOT_SERVER_CONFIG_PATH = Path.home() / ".config" / "bbot_server" / "config.yml"

# Create the config if it doesn't exist
if not BBOT_SERVER_CONFIG_PATH.exists():
    try:
        BBOT_SERVER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        BBOT_SERVER_CONFIG_PATH.touch(mode=0o600)
        # fill with commented defaults
        with open(BBOT_SERVER_CONFIG_PATH, "w") as f:
            yaml_str = OmegaConf.to_yaml(BBOT_SERVER_DEFAULTS)
            commented_yaml = "\n".join([f"# {line}" for line in yaml_str.split("\n")])
            f.write(f"# NOTICE: This file is commented by default. Uncomment it to make changes.\n")
            f.write(commented_yaml)
    except Exception as e:
        log.error(f"Error creating config file at {BBOT_SERVER_CONFIG_PATH}: {e}")


def refresh_api_keys():
    global VALID_API_KEYS
    api_keys = set()
    for key in ("api_keys", "api_key"):
        keys = BBOT_SERVER_CONFIG.get(key, [])
        if keys:
            if isinstance(keys, str):
                keys = [keys]
            api_keys.update(keys)
    VALID_API_KEYS = api_keys


def refresh_config(custom_config_path=None):
    """
    Refresh the config.
    """
    global BBOT_SERVER_CONFIG_PATH, BBOT_SERVER_CONFIG, BBOT_SERVER_URL

    if custom_config_path:
        os.environ["BBOT_SERVER_CONFIG"] = str(custom_config_path)

    # if a custom config is provided, merge it with the defaults
    config_path = Path(os.environ.get("BBOT_SERVER_CONFIG", BBOT_SERVER_CONFIG_PATH))
    if config_path.exists():
        BBOT_SERVER_CONFIG_PATH = config_path
        try:
            config = OmegaConf.load(BBOT_SERVER_CONFIG_PATH)
            BBOT_SERVER_CONFIG = OmegaConf.merge(BBOT_SERVER_DEFAULTS, config)
        except Exception as e:
            log.error(f"Error loading config file at {BBOT_SERVER_CONFIG_PATH}: {e}")
    else:
        log.warning(f"No config file found at {BBOT_SERVER_CONFIG_PATH}, using defaults")

    BBOT_SERVER_URL = BBOT_SERVER_CONFIG.url
    refresh_api_keys()
    return BBOT_SERVER_CONFIG


def check_api_key(api_key: str):
    global VALID_API_KEYS
    try:
        api_key = str(UUID(api_key))
    except ValueError:
        return False, "API key must be a valid UUID"
    # if the API key is invalid, try refreshing the config
    if api_key not in VALID_API_KEYS:
        refresh_config()
        if api_key not in VALID_API_KEYS:
            return False, "Invalid API key"
    return True, "Valid API key"


refresh_config()
