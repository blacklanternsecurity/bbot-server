from omegaconf import OmegaConf

from bbot_server.config import BBOT_SERVER_CONFIG


class BaseDB:
    config_key = None

    def __init__(self, config=None):
        self.global_config = BBOT_SERVER_CONFIG
        try:
            self.config = self.global_config[self.config_key]
            if config is not None:
                self.config = OmegaConf.merge(self.config, config)
        except Exception as e:
            raise ValueError("Event store configuration is missing") from e
        try:
            self.uri = self.config.uri
        except Exception as e:
            raise ValueError("Event store URI is missing") from e

        self._setup_finished = False

    @property
    def db_name(self):
        if self.config.uri.count("/") == 3:
            db_name = self.config.uri.split("/")[-1]
            if not db_name:
                raise ValueError("Database name must be included in the URI.")
            return db_name
        raise ValueError(f"Invalid URI: {self.config.uri} - Database name must be included.")

    @property
    def table_name(self):
        table_name = self.config.table_name
        if not table_name:
            raise ValueError("Table name must be included in the configuration.")
        return table_name

    async def setup(self):
        if not self._setup_finished:
            await self._setup()
            self._setup_finished = True

    async def _setup(self):
        raise NotImplementedError()
