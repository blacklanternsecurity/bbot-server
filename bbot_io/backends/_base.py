import logging
from functools import partial


class BaseTable:
    def __init__(self, backend, table_name, data_model):
        self.backend = backend
        self.table_name = table_name
        self.model = data_model

    async def setup(self):
        raise NotImplementedError

    async def find(self):
        raise NotImplementedError

    async def find_one(self):
        raise NotImplementedError

    async def insert(self, obj):
        return await self._insert(obj)


class BaseBackend:

    table_class = BaseTable
    protocol = ""
    default_database = "bbot"
    default_username = ""
    default_password = ""
    default_host = "127.0.0.1"
    default_port = 0

    def __init__(self, *args, **kwargs):
        self.log = logging.getLogger(f"bbot.io.backends.{self.__class__.__name__}")
        self.database = kwargs.pop("database", self.default_database)
        self.username = kwargs.pop("username", self.default_username)
        self.password = kwargs.pop("password", self.default_password)
        self.host = kwargs.pop("host", self.default_host)
        self.port = kwargs.pop("port", self.default_port)

        from bbot_io import config

        self.config = config
        self.tables = []
        self.setup = partial(self.setup, *args, **kwargs)

    async def get_table(self, applet):
        if applet.model:
            table = self.table_class(self, applet.name.lower(), applet.model)
            self.tables.append(table)
            return table

    async def _setup(self):
        for table in self.tables:
            await table.setup()
        await self.setup()

    async def setup(self):
        pass
