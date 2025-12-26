"""Database configuration and session management.

Provides async SQLAlchemy engine and session factory for database operations.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Create async engine with asyncpg driver
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,  # Check connection health before use
    pool_size=5,
    max_overflow=10,
)

# Session factory for creating database sessions
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession]:
    """Provide a database session for dependency injection.

    Yields:
        AsyncSession: An async database session.

    Example:
        @router.get("/items")
        async def get_items(db: Annotated[AsyncSession, Depends(get_db)]):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
