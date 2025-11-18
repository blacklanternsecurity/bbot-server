import uuid
import logging
from pathlib import Path
from typing import Any, Iterable, Optional, Set

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
DEFAULT_CONFIG_PATH = Path.home() / ".config" / "bbot_server" / "config.yml"
CUSTOM_YAML_PATH = None

# Create the config if it doesn't exist
if not DEFAULT_CONFIG_PATH.exists():
    try:
        DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_CONFIG_PATH.touch(mode=0o600)
        # fill with commented defaults
        with open(DEFAULT_CONFIG_PATH, "w") as f:
            with open(BBOT_SERVER_DEFAULTS_PATH, "r") as defaults_file:
                defaults_content = defaults_file.read()
            f.write(f"# NOTICE: This file is commented by default. Uncomment it to make changes.\n")
            f.write("\n".join([f"# {line}" for line in defaults_content.split("\n")]))
    except Exception as e:
        log.error(f"Error creating config file at {DEFAULT_CONFIG_PATH}: {e}")


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
    api_key: Optional[uuid.UUID] = None
    api_keys: Iterable[uuid.UUID] = Field(default_factory=list)

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

    # runtime-only value of config path
    _config_path: Optional[Path] = PrivateAttr(default=None)

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
        global CUSTOM_YAML_PATH

        # if the user asked for a custom config path, use it
        custom_yaml_path = init_settings.init_kwargs.get("config_path", CUSTOM_YAML_PATH)
        # otherwise, if we previously had a custom config path, use it
        if not custom_yaml_path and CUSTOM_YAML_PATH:
            custom_yaml_path = CUSTOM_YAML_PATH
        # if we have a custom config path, add it to the yaml paths
        if custom_yaml_path:
            config_path = Path(custom_yaml_path)
            CUSTOM_YAML_PATH = custom_yaml_path
        # otherwise, use the default config path
        else:
            config_path = DEFAULT_CONFIG_PATH

        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls, yaml_file=[BBOT_SERVER_DEFAULTS_PATH, config_path]),
            file_secret_settings,
        )

    def refresh(self, **overrides):
        """
        Re-read the config from disk and environment.
        """
        # Instantiate or re-init the settings object; BaseSettings will pull in:
        #   - init overrides
        #   - env vars (BBOT_SERVER_*)
        #   - YAML defaults/user config via YamlConfigSettingsSource

        # preserve the existing yaml paths
        # if not "config_path" in overrides:
        #     overrides["config_path"] = self._yaml_paths

        self.__init__(**overrides)
        self.refresh_api_keys()

    # --- API key helpers, all on the settings class ---

    def refresh_api_keys(self) -> None:
        """
        Populate the in-memory set of valid API keys from this config.
        """
        api_keys = set()

        # Single api_key, if set
        if self.api_key:
            try:
                api_keys.add(self.api_key)
            except ValueError as e:
                raise BBOTServerValueError("Invalid API key in config") from e

        # List of api_keys
        for key in self.api_keys:
            try:
                api_keys.add(key)
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
                return self.api_key
            except ValueError:
                pass

        # otherwise, return the first valid API key
        try:
            return next(iter(self._valid_api_keys))
        except StopIteration:
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
        api_key = uuid.uuid4()
        self._valid_api_keys.add(api_key)
        # keep api_keys field in sync for future refreshes
        self.api_keys = sorted(self._valid_api_keys, key=str)
        return api_key

    def revoke_api_key(self, api_key: str) -> None:
        """
        Revoke an API key from the in-memory config.
        """
        try:
            parsed = uuid.UUID(api_key)
        except ValueError as e:
            raise BBOTServerValueError("Invalid API key") from e

        self._valid_api_keys.discard(parsed)


BBOT_SERVER_CONFIG = BBOTServerSettings()
