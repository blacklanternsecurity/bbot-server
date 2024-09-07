import logging
from functools import partial


class BaseTable:
    def __init__(self, backend, table_name, data_model):
        self.backend = backend
        self.table_name = table_name
        self.model = data_model

    async def setup(self):
        pass

    async def find(self):
        raise NotImplementedError

    async def find_one(self):
        raise NotImplementedError

    async def insert(self, obj):
        raise NotImplementedError

    async def count(self):
        raise NotImplementedError

    def __str__(self):
        return f"{self.__class__.__name__}({self.table_name})"


class BaseBackend:
    """
    Backends abstract the database -- postgres, sqlite, etc.

    User --> Interface --> Applets --> Backend

    They accept SQLAlchemy query objects, and return pydantic models
    """

    table_class = BaseTable
    protocol = ""
    default_database = "bbot"
    default_username = ""
    default_password = ""
    default_host = "127.0.0.1"
    default_port = 0

    def __init__(self, *args, **kwargs):
        self.log = logging.getLogger(f"bbot.server.backends.{self.__class__.__name__}")
        self.database = kwargs.pop("database", self.default_database)
        self.username = kwargs.pop("username", self.default_username)
        self.password = kwargs.pop("password", self.default_password)
        self.host = kwargs.pop("host", self.default_host)
        self.port = kwargs.pop("port", self.default_port)

        from bbot_io import config

        self.config = config
        self.tables = []
        self.setup = partial(self.setup, *args, **kwargs)
        self._setup_done = False

    async def make_table(self, applet):
        """
        Create a table for an applet based on its name and model
        """
        if applet.model:
            table = self.table_class(self, applet.name.lower(), applet.model)
            await table.setup()
            self.tables.append(table)
            return table

    async def _setup(self):
        if not self._setup_done:
            self._setup_done = True
            await self.setup()

    async def setup(self):
        pass
