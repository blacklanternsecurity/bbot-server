import logging

from bbot_server.config import BBOT_SERVER_CONFIG as bbcfg
from bbot_server.errors import BBOTServerValueError


class BaseDB:
    # config_key is used for looking up the config for this specific db store
    # e.g. "event_store" or "asset_store" or "user_store"
    config_key = None

    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.config = bbcfg

        if not self.db_config:
            raise BBOTServerValueError(
                f"Database configuration (`{self.config_key}`) is missing from config: {self.config}"
            )
        if not self.uri:
            raise BBOTServerValueError(f"Database URI is missing from config: {self.db_config}")

        self.log.debug(f"Setting up {self.__class__.__name__} at {self.uri}")

        self._setup_finished = False

    @property
    def db_config(self):
        return getattr(self.config, self.config_key, None)

    @property
    def uri(self):
        uri = getattr(self.db_config, "uri", "")
        if not uri:
            raise BBOTServerValueError(f"Database URI is missing from config: {self.db_config}")
        return uri

    @property
    def db_name(self):
        if self.uri.count("/") == 3:
            db_name = self.uri.split("/")[-1]
            if not db_name:
                raise BBOTServerValueError("Database name must be included in the URI.")
            return db_name
        raise BBOTServerValueError(f"Invalid URI: {self.uri} - Database name must be included.")

    async def setup(self):
        if not self._setup_finished:
            await self._setup()
            self._setup_finished = True

    async def _setup(self):
        """
        Setup method to be overridden by subclasses
        """
        raise NotImplementedError()

    async def cleanup(self):
        """
        Cleanup method to be overridden by subclasses
        """
        pass
