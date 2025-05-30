import os
import uuid
import logging
from pathlib import Path
from omegaconf import OmegaConf

from bbot_server.errors import BBOTServerError


log = logging.getLogger("bbot_server.config")


BBOT_SERVER_DIR = Path(__file__).parent
API_KEY_NAME = "X-API-Key"
VALID_API_KEYS = set()
API_KEY = ""

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


def update_config_path(config_path):
    os.environ["BBOT_SERVER_CONFIG"] = str(config_path)
    refresh_config()


def update_config(config):
    """
    Update the config with a new config
    """
    global BBOT_SERVER_CONFIG
    BBOT_SERVER_CONFIG = OmegaConf.merge(BBOT_SERVER_CONFIG, config)
    refresh_config()


def refresh_config():
    """
    Re-read the config from disk
    """
    global BBOT_SERVER_CONFIG_PATH, BBOT_SERVER_CONFIG, BBOT_SERVER_URL

    # if a custom config is provided, merge it with the defaults
    config_path = Path(os.environ.get("BBOT_SERVER_CONFIG", BBOT_SERVER_CONFIG_PATH))
    log.critical(f"config_path: {config_path}")
    if config_path.exists():
        if str(config_path) != str(BBOT_SERVER_CONFIG_PATH):
            log.debug(f"Changing config to point to {config_path} (was {BBOT_SERVER_CONFIG_PATH})")
            BBOT_SERVER_CONFIG_PATH = config_path
        try:
            config = OmegaConf.load(BBOT_SERVER_CONFIG_PATH)
            BBOT_SERVER_CONFIG = OmegaConf.merge(BBOT_SERVER_DEFAULTS, config)
        except Exception as e:
            log.error(f"Error loading config file at {BBOT_SERVER_CONFIG_PATH}: {e}")
    else:
        log.warning(f"No config file found at {config_path}, using defaults")

    try:
        BBOT_SERVER_URL = BBOT_SERVER_CONFIG.url
    except Exception as e:
        raise BBOTServerError(f"Config must contain a `url` field") from e

    event_store_uri = os.environ.get("BBOT_SERVER_EVENT_STORE_MONGO_URI", "")
    if event_store_uri:
        BBOT_SERVER_CONFIG.event_store.uri = event_store_uri
    asset_store_uri = os.environ.get("BBOT_SERVER_ASSET_STORE_MONGO_URI", "")
    if asset_store_uri:
        BBOT_SERVER_CONFIG.asset_store.uri = asset_store_uri
    user_store_uri = os.environ.get("BBOT_SERVER_USER_STORE_MONGO_URI", "")
    if user_store_uri:
        BBOT_SERVER_CONFIG.user_store.uri = user_store_uri
    redis_uri = os.environ.get("BBOT_SERVER_REDIS_URI", "")
    if redis_uri:
        BBOT_SERVER_CONFIG.message_queue.uri = redis_uri
    refresh_api_keys()
    return BBOT_SERVER_CONFIG


def refresh_api_keys():
    """
    Get the API keys from the config
    """
    global VALID_API_KEYS
    api_keys = set()
    for key in ("api_keys", "api_key"):
        keys = BBOT_SERVER_CONFIG.get(key, [])
        if keys:
            if isinstance(keys, str):
                keys = [keys]
            api_keys.update(keys)
    VALID_API_KEYS = api_keys


def get_api_keys():
    """
    Get the API keys from the config
    """
    return VALID_API_KEYS


def get_api_key():
    try:
        return next(iter(VALID_API_KEYS))
    except StopIteration:
        raise BBOTServerError("No API keys found. Please set `api_keys` in your config file")


def check_api_key(api_key: str):
    """
    Check whether an API key is valid
    """
    global VALID_API_KEYS
    if not api_key:
        return False, "API key is required"
    try:
        api_key = str(uuid.UUID(api_key))
    except Exception:
        return False, "API key must be a valid UUID"
    # if the API key is invalid, try refreshing the config
    if api_key not in VALID_API_KEYS:
        refresh_config()
        if api_key not in VALID_API_KEYS:
            return False, f'Invalid API key "{api_key}" not in {VALID_API_KEYS}'
    return True, "Valid API key"


def add_api_key():
    """
    Add a new API key to the config.

    Note: writes the config to disk
    """
    global VALID_API_KEYS
    api_key = str(uuid.uuid4())
    VALID_API_KEYS.add(api_key)
    BBOT_SERVER_CONFIG["api_keys"] = sorted(VALID_API_KEYS)

    # write new API key to config
    existing_config = OmegaConf.load(BBOT_SERVER_CONFIG_PATH)
    existing_api_keys = set(existing_config.get("api_keys", []))
    existing_api_keys.add(api_key)
    existing_config["api_keys"] = sorted(existing_api_keys)
    OmegaConf.save(existing_config, BBOT_SERVER_CONFIG_PATH)

    # refresh config by reading it from disk
    refresh_config()
    return api_key


def revoke_api_key(api_key: str):
    """
    Revoke an API key from the config.
    """
    global VALID_API_KEYS
    VALID_API_KEYS.remove(str(api_key))
    refresh_config()


refresh_config()
