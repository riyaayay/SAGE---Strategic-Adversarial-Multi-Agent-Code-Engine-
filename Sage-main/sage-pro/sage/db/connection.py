"""
SAGE-PRO Database Connection
═════════════════════════════
Async PostgreSQL connection pool via asyncpg + SQLAlchemy.
Connection string from env var DATABASE_URL.
"""

import os
import structlog
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

logger = structlog.get_logger(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://sage:sage@localhost:5432/sage_pro",
)

engine = create_async_engine(DATABASE_URL, echo=False, pool_size=10, max_overflow=20)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    """Yields an async database session.

    Usage:
        async with get_session() as session:
            ...
    """
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """Creates all tables if they don't exist."""
    from sage.db.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_initialized", url=DATABASE_URL.split("@")[-1])
