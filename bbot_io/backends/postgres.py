from ._sqlbase import SQLBackend


class postgres(SQLBackend):
    """
    docker run --rm -e POSTGRES_PASSWORD=bbotislife -p 5432:5432 postgres
    """

    protocol = "postgresql"
    default_username = "postgres"
    default_password = "postgres"
