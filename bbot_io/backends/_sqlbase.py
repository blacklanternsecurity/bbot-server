from sqlmodel import Session, SQLModel, select, delete, create_engine
from sqlalchemy_utils.functions import database_exists, create_database

from bbot_io.backends._base import BaseBackend, BaseTable


class SQLTable(BaseTable):

    @property
    def select(self):
        return select(self.model)

    async def find(self):
        with Session(self.backend.engine) as session:
            statement = select(self.model)
            result = session.exec(statement)
            return result.all()

    async def find_one(self):
        pass

    async def exec(self, statement):
        with Session(self.backend.engine) as session:
            return session.exec(statement).all()

    async def insert(self, obj):
        with Session(self.backend.engine, expire_on_commit=False) as session:
            session.add(obj)
            session.commit()

    def clear(self):
        with Session(self.backend.engine) as session:
            stmt = delete(self.model)
            session.exec(stmt)
            session.commit()


class SQLBackend(BaseBackend):

    table_class = SQLTable

    async def setup(self):
        if not database_exists(self.connection_string):
            create_database(self.connection_string)
        self.engine = create_engine(self.connection_string)
        SQLModel.metadata.create_all(self.engine)

    @property
    def connection_string(self):
        connection_string = f"{self.protocol}://"
        if self.username:
            connection_string += f"{self.username}:{self.password}"
        if self.host:
            connection_string += f"@{self.host}"
            if self.port:
                connection_string += f":{self.port}"
        if self.database:
            connection_string += f"/{self.database}"
        return connection_string

    async def drop_database(self):
        for table in self.tables:
            table.clear()
