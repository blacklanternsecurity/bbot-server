from typing import Union
from pathlib import Path
from contextlib import suppress
from sqlmodel import Session

from ._sqlbase import SQLBackend


class postgres(SQLBackend):

    protocol = "postgresql"
    default_username = "postgres"
    default_password = "postgres"
