from .base import IOTestBase


class TestPostgres(IOTestBase):
    backend = "postgres"
    kwargs = dict(password="bbotislife")
