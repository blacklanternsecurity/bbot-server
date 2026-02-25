import logging

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import SQLModel

from bbot_server.config import BBOT_SERVER_CONFIG as bbcfg

# Import table models so SQLModel.metadata knows about them
import bbot_server.db.tables  # noqa: F401
import bbot_server.modules.events.events_models  # noqa: F401
import bbot_server.modules.activity.activity_models  # noqa: F401
import bbot_server.modules.findings.findings_models  # noqa: F401

log = logging.getLogger("bbot_server.db.postgres")


async def create_db():
    """
    Create the async engine and session factory for PostgreSQL.

    Returns:
        tuple: (engine, session_factory)
    """
    uri = bbcfg.database.uri
    log.info(f"Connecting to PostgreSQL at {uri}")
    engine = create_async_engine(uri, echo=False, pool_size=10, max_overflow=20)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Create tables (dev/test). In production, use Alembic.
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    log.info("PostgreSQL connection established and tables created")
    return engine, session_factory
