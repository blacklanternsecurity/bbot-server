from pathlib import Path
from omegaconf import OmegaConf


BBOT_SERVER_DIR = Path(__file__).parent.parent

# Create the config if it doesn't exist

config_file = Path.home() / ".config" / "bbot_server" / "config.yml"
if not config_file.exists():
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.touch()

# Load defaults

default_config_file = BBOT_SERVER_DIR / "defaults.yml"
default_config = OmegaConf.load(default_config_file)

# Load config

config = OmegaConf.load(config_file)

# Merge defaults and config

BBOT_SERVER_CONFIG = OmegaConf.merge(default_config, config)
