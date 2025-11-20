import os
import uuid
import yaml
import logging
from pathlib import Path
from typing import Any, Optional, Set, List

from pydantic import BaseModel, Field, PrivateAttr
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from bbot_server.errors import BBOTServerError, BBOTServerValueError


log = logging.getLogger("bbot_server.config")


BBOT_SERVER_DIR = Path(__file__).parent
BBOT_SERVER_DEFAULTS_PATH = BBOT_SERVER_DIR / "defaults.yml"
BBOT_SERVER_CONFIG_PATH = Path.home() / ".config" / "bbot_server" / "config.yml"

# Create the config if it doesn't exist
if not BBOT_SERVER_CONFIG_PATH.exists():
    try:
        BBOT_SERVER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        BBOT_SERVER_CONFIG_PATH.touch(mode=0o600)
        # fill with commented defaults
        with open(BBOT_SERVER_CONFIG_PATH, "w") as f:
            with open(BBOT_SERVER_DEFAULTS_PATH, "r") as defaults_file:
                defaults_content = defaults_file.read()
            f.write(f"# NOTICE: This file is commented by default. Uncomment it to make changes.\n")
            f.write("\n".join([f"# {line}" for line in defaults_content.split("\n")]))
    except Exception as e:
        log.error(f"Error creating config file at {BBOT_SERVER_CONFIG_PATH}: {e}")


class StoreConfig(BaseModel):
    uri: str


class MessageQueueConfig(BaseModel):
    uri: str


class AgentConfig(BaseModel):
    base_preset: dict[str, Any] = Field(default_factory=dict)


class CLIConfig(BaseModel):
    http_timeout: int = 90


class BBOTServerSettings(BaseSettings):
    """
    Minimal, typed BBOT server configuration.

    Sources (in order):
      1. init kwargs (tests / in-process overrides)
      2. environment variables (BBOT_SERVER_*)
      3. YAML files: defaults.yml, user config.yml
      4. file secrets (unused for now)
    """

    # core
    url: str

    # API key config
    auth_enabled: bool = True
    auth_header: str = "X-API-Key"
    api_key: Optional[str] = None
    api_keys: List[str] = Field(default_factory=list)

    # storage + mq
    event_store: StoreConfig
    asset_store: StoreConfig
    user_store: StoreConfig
    message_queue: MessageQueueConfig

    # misc nested config we know about
    agent: Optional[AgentConfig] = Field(default_factory=AgentConfig)
    cli: Optional[CLIConfig] = Field(default_factory=CLIConfig)

    # individual module configs
    modules: Optional[dict[str, dict[str, Any]]] = Field(default_factory=dict)

    # runtime-only cache of parsed API keys
    _valid_api_keys: Set[uuid.UUID] = PrivateAttr(default_factory=set)

    # defaults + env wiring
    model_config = SettingsConfigDict(
        env_prefix="BBOT_SERVER_",
        env_nested_delimiter="__",
        extra="allow",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type["BBOTServerSettings"],
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        """
        Wire up Pydantic's YAML source with our two YAML files.
        """
        # we preserve custom yaml paths for future refreshes
        global BBOT_SERVER_CONFIG_PATH

        # if the user asked for a custom config path, use it
        custom_config_path = init_settings.init_kwargs.get("config_path", None) or os.environ.get(
            "BBOT_SERVER_CONFIG", None
        )
        # if custom path is provided, override it for future refreshes
        if custom_config_path:
            BBOT_SERVER_CONFIG_PATH = Path(custom_config_path)

        log.info(f"Loading config files from: {BBOT_SERVER_DEFAULTS_PATH}, {BBOT_SERVER_CONFIG_PATH}")
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls, yaml_file=[BBOT_SERVER_DEFAULTS_PATH, BBOT_SERVER_CONFIG_PATH]),
            file_secret_settings,
        )

    def refresh(self, **overrides):
        """
        Re-read the config from disk and environment.
        """
        self.__init__(**overrides)
        self.refresh_api_keys()

    def refresh_api_keys(self) -> None:
        """
        Populate the in-memory set of valid API keys from this config.
        """
        api_keys = set()

        # Single api_key, if set
        if self.api_key:
            try:
                api_keys.add(uuid.UUID(self.api_key))
            except ValueError as e:
                raise BBOTServerValueError("Invalid API key in config") from e

        # List of api_keys
        for key in self.api_keys:
            try:
                api_keys.add(uuid.UUID(key))
            except ValueError as e:
                raise BBOTServerValueError("Invalid API key in config") from e

        self._valid_api_keys = api_keys

    def get_api_keys(self) -> Set[uuid.UUID]:
        """
        Return the set of valid API keys.
        """
        return self._valid_api_keys

    def get_api_key(self) -> str:
        """
        Return a single API key string, preferring the explicit api_key field.
        """
        # prioritize single api key if set
        if self.api_key:
            try:
                return uuid.UUID(self.api_key)
            except ValueError:
                pass

        # otherwise, return the first valid API key
        try:
            return str(next(iter(self._valid_api_keys)))
        except StopIteration:
            self.refresh()
            raise BBOTServerError(
                "No API keys found in the config. Please set `api_keys` in your config file "
                "or run `bbctl server apikey add`"
            )

    def check_api_key(self, api_key: str):
        """
        Check whether an API key is valid.
        """
        if not api_key:
            return False, "API key is required"
        try:
            parsed = uuid.UUID(api_key)
        except Exception:
            return False, "API key must be a valid UUID"

        # if the API key is invalid, try refreshing the config
        if parsed not in self._valid_api_keys:
            self.refresh()
            if parsed not in self._valid_api_keys:
                return False, f'Invalid API key "{api_key}"'
        return True, "Valid API key"

    def add_api_key(self) -> uuid.UUID:
        """
        Add a new API key to the in-memory config.

        NOTE: for now this only affects process memory; persistence to disk
        can be wired in later when we tighten the design.
        """
        log.info(f"Adding new API key")
        api_key = uuid.uuid4()
        self._valid_api_keys.add(api_key)
        self.write_api_keys()
        return api_key

    def revoke_api_key(self, api_key: str) -> None:
        try:
            parsed = uuid.UUID(api_key)
        except ValueError as e:
            raise BBOTServerValueError("Invalid API key") from e

        # remove the API key from the config
        self._valid_api_keys.discard(parsed)
        self.write_api_keys()
        self.refresh()

    def write_api_keys(self):
        with open(BBOT_SERVER_CONFIG_PATH, "r") as f:
            config_yaml = yaml.safe_load(f) or {}
        # add the new API key to the config
        api_key = self.api_key or config_yaml.get("api_key", None)
        api_keys = [str(key) for key in self._valid_api_keys]
        if api_key:
            api_keys = sorted([k for k in api_keys if not k == api_key])
            config_yaml["api_key"] = api_key
        if api_keys:
            config_yaml["api_keys"] = api_keys

        num_api_keys = len(api_keys) + (1 if api_key else 0)
        if num_api_keys > 0:
            log.info(f"Writing {num_api_keys:,} API keys to config file at {BBOT_SERVER_CONFIG_PATH}")
            # save the config file
            with open(BBOT_SERVER_CONFIG_PATH, "w") as f:
                yaml.safe_dump(config_yaml, f)


BBOT_SERVER_CONFIG = BBOTServerSettings()
