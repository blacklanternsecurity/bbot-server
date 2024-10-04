from typing import Union
from pathlib import Path

from ._sqlbase import SQLBackend


class sqlite(SQLBackend):
    options = {"database": "Path to sqlite db"}
    default_database = "bbot.db"

    async def setup(self, database: Union[str, Path, None] = None):
        if database is None:
            self.database = self.config.home / "bbot.db"
        else:
            self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        await super().setup()

    def connection_string(self, mask_password=False):
        return f"sqlite:///{self.database}"
