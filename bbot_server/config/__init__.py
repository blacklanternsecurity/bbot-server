import os
import logging
from pathlib import Path
from omegaconf import OmegaConf

log = logging.getLogger("bbot_server.config")


BBOT_SERVER_DIR = Path(__file__).parent.parent

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
            f.write(f"# NOTICE: This file is commented out by default. Uncomment it to make changes.\n")
            f.write(commented_yaml)
    except Exception as e:
        log.error(f"Error creating config file at {BBOT_SERVER_CONFIG_PATH}: {e}")

# if a custom config is provided, merge it with the defaults
custom_config_path = os.environ.get("BBOT_SERVER_CONFIG", "")
if custom_config_path and Path(custom_config_path).exists():
    BBOT_SERVER_CONFIG_PATH = Path(custom_config_path)
    try:
        custom_config = OmegaConf.load(BBOT_SERVER_CONFIG_PATH)
        BBOT_SERVER_CONFIG = OmegaConf.merge(BBOT_SERVER_DEFAULTS, custom_config)
    except Exception as e:
        log.error(f"Error loading custom config file at {BBOT_SERVER_CONFIG_PATH}: {e}")

BBOT_SERVER_URL = BBOT_SERVER_CONFIG.url
