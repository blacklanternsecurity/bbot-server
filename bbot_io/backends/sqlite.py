from typing import Union
from pathlib import Path
from contextlib import suppress
from sqlmodel import Session

from ._sqlbase import SQLBackend


class sqlite(SQLBackend):

    async def setup(self, database: Union[str, Path] = None):
        if not self.database:
            self.database = self.config.home / "bbot.db"
        self.database = Path(self.database).resolve()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        await super().setup()

    @property
    def connection_string(self):
        return f"sqlite:///{self.database}"
