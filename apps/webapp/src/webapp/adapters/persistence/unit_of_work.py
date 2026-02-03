"""Unit of Work pattern for transaction management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if TYPE_CHECKING:
    from types import TracebackType


class UnitOfWork:
    """Unit of Work for managing database transaction boundaries.

    Implements async context manager protocol for automatic transaction
    handling. Supports explicit commit() and rollback() operations.

    Example:
        async with UnitOfWork(session_factory) as uow:
            user = await user_repository.get_by_id(user_id)
            user.email = "new@example.com"
            await user_repository.save(user)
            await uow.commit()
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Initialize UnitOfWork with a session factory.

        Args:
            session_factory: SQLAlchemy async session factory
        """
        self.session_factory = session_factory
        self._session: AsyncSession | None = None

    @property
    def session(self) -> AsyncSession:
        """Get the current session.

        Returns:
            The active AsyncSession

        Raises:
            RuntimeError: If accessed outside of context manager
        """
        if self._session is None:
            raise RuntimeError("UnitOfWork must be used as a context manager")
        return self._session

    async def __aenter__(self) -> UnitOfWork:
        """Enter async context manager, creating a new session.

        Returns:
            Self for context manager protocol
        """
        self._session = self.session_factory()
        await self._session.begin()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit async context manager, handling commit/rollback.

        If an exception occurred, rollback the transaction.
        Otherwise, if not explicitly committed, rollback by default.

        Args:
            exc_type: Exception type if raised
            exc_val: Exception value if raised
            exc_tb: Exception traceback if raised
        """
        if self._session is None:
            return

        try:
            if exc_type is not None:
                # Exception occurred - rollback
                await self.rollback()
            # If no exception but transaction still pending, rollback
            # (explicit commit() required for changes to persist)
            elif self._session.in_transaction():
                await self.rollback()
        finally:
            await self._session.close()
            self._session = None

    async def commit(self) -> None:
        """Commit the current transaction.

        Raises:
            RuntimeError: If called outside of context manager
        """
        if self._session is None:
            raise RuntimeError("Cannot commit outside of context manager")
        await self._session.commit()

    async def rollback(self) -> None:
        """Rollback the current transaction.

        Raises:
            RuntimeError: If called outside of context manager
        """
        if self._session is None:
            raise RuntimeError("Cannot rollback outside of context manager")
        await self._session.rollback()
