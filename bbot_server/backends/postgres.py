from ._sqlbase import SQLBackend


class postgres(SQLBackend):
    """
    docker run --rm -e POSTGRES_PASSWORD=bbotislife -p 5432:5432 postgres
    """

    options = {
        "database": "Postgres database name",
        "username": "Postgres username",
        "password": "Postgres password",
        "host": "Hostname of Postgres server",
        "port": "Port of Postgres server",
    }

    protocol = "postgresql"
    default_username = "postgres"
    default_password = "postgres"
