import logging


class BaseDB:
    config_key = None

    def __init__(self, config):
        self.log = logging.getLogger(__name__)
        self.config = config
        try:
            self.db_config = config[self.config_key]
        except Exception as e:
            raise ValueError(f"'{self.config_key}' is missing from config") from e
        try:
            self.uri = self.db_config.uri
        except Exception as e:
            raise ValueError("Event store URI is missing") from e

        self.log.debug(f"Setting up {self.__class__.__name__} at {self.uri}")

        self._setup_finished = False

    @property
    def db_name(self):
        if self.db_config.uri.count("/") == 3:
            db_name = self.db_config.uri.split("/")[-1]
            if not db_name:
                raise ValueError("Database name must be included in the URI.")
            return db_name
        raise ValueError(f"Invalid URI: {self.db_config.uri} - Database name must be included.")

    @property
    def table_name(self):
        table_name = self.db_config.table_name
        if not table_name:
            raise ValueError("Table name must be included in the configuration.")
        return table_name

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
