from . import IOTestBase

# docker run --rm -e POSTGRES_PASSWORD=bbotislife -p 5432:5432 postgres


class TestPostgres(IOTestBase):
    backend = "postgres"
    kwargs = dict(password="bbotislife")
