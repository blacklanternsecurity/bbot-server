from sqlalchemy import func, inspect
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select, delete, create_engine
from sqlalchemy_utils.functions import database_exists, create_database

from bbot_io.backends._base import BaseBackend, BaseTable


class SQLTable(BaseTable):

    @property
    def select(self):
        return select(self.model)

    async def exec(self, statement):
        with Session(self.backend.engine) as session:
            return session.exec(statement).all()

    async def find(self):
        with Session(self.backend.engine) as session:
            statement = select(self.model)
            result = session.exec(statement)
            return result.all()

    async def find_one(self):
        pass

    async def insert(self, obj):
        with Session(self.backend.engine, expire_on_commit=False) as session:
            session.add(obj)
            session.commit()

    async def insert_if_not_exists(self, obj):
        with Session(self.backend.engine, expire_on_commit=False) as session:
            # Get the primary key columns
            mapper = inspect(obj.__class__)
            pk_columns = mapper.primary_key

            # Construct a filter condition for all primary key columns
            filter_condition = {col.name: getattr(obj, col.name) for col in pk_columns}

            try:
                # Check if an object with the same primary key already exists
                existing = session.execute(select(obj.__class__).filter_by(**filter_condition)).scalar_one_or_none()

                if existing is None:
                    session.add(obj)
                    session.commit()
                # If it exists, we do nothing (effectively a no-op)
            except IntegrityError:
                session.rollback()

    async def count(self):
        with Session(self.backend.engine) as session:
            return session.exec(func.count(self.model.row_id)).scalar()

    def clear(self):
        with Session(self.backend.engine) as session:
            statement = delete(self.model)
            session.exec(statement)
            session.commit()


class SQLBackend(BaseBackend):

    table_class = SQLTable

    async def setup(self):
        self.log.info(f"Connecting to {self.connection_string(mask_password=True)}")
        if not database_exists(self.connection_string()):
            create_database(self.connection_string())
        self.engine = create_engine(self.connection_string())
        SQLModel.metadata.create_all(self.engine)

    def connection_string(self, mask_password=False):
        connection_string = f"{self.protocol}://"
        if self.username:
            password = self.password
            if mask_password:
                password = "****"
            connection_string += f"{self.username}:{password}"
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
