import os
from pathlib import Path
from omegaconf import OmegaConf


BBOT_SERVER_DIR = Path(__file__).parent.parent

# Create the config if it doesn't exist

config_file = Path.home() / ".config" / "bbot_server" / "config.yml"
if not config_file.exists():
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.touch()

# Load defaults

BBOT_SERVER_DEFAULTS_PATH = BBOT_SERVER_DIR / "defaults.yml"
BBOT_SERVER_DEFAULTS = OmegaConf.load(BBOT_SERVER_DEFAULTS_PATH)
BBOT_SERVER_CONFIG = BBOT_SERVER_DEFAULTS

# if a custom config is provided, merge it with the defaults

custom_config_path = os.environ.get("BBOT_SERVER_CONFIG", "")
if custom_config_path and Path(custom_config_path).exists():
    custom_config = OmegaConf.load(custom_config_path)
    BBOT_SERVER_CONFIG = OmegaConf.merge(BBOT_SERVER_DEFAULTS, custom_config)

BBOT_SERVER_URL = BBOT_SERVER_CONFIG.url
