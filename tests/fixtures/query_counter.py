"""Query counting fixture for integration tests.

Provides a context manager to count SQL queries executed during a test.
Uses SQLAlchemy event system to intercept and count queries.

Created for T42: Add query counting fixture for integration tests
"""

from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlalchemy import event

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.ext.asyncio import AsyncSession


@contextmanager
def assert_query_count(
    session: "AsyncSession",
    expected: int,
) -> "Generator[None, None, None]":
    """Count SQL queries executed within the context and assert the count.

    Args:
        session: The SQLAlchemy async session to monitor
        expected: The expected number of queries

    Raises:
        AssertionError: If the actual query count doesn't match expected

    Example:
        >>> with assert_query_count(session, expected=1):
        ...     await session.execute(select(User))
    """
    query_count = 0

    def _count_query(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        """Event listener that increments query count.

        Filters out lazy-loaded cascade queries (e.g., relationship loads
        triggered by delete operations) to count only explicit queries.
        """
        nonlocal query_count

        # Skip lazy-loaded queries triggered by cascade operations
        # These have _lazy_loaded_from in their execution_options
        if context:
            exec_opts = context.execution_options
            if exec_opts and "_sa_orm_load_options" in exec_opts:
                load_opts = exec_opts["_sa_orm_load_options"]
                # Check if this is a lazy-loaded query (has _lazy_loaded_from attribute)
                if hasattr(load_opts, "_lazy_loaded_from"):
                    return  # Don't count cascade-triggered queries

        query_count += 1

    # Get the engine from the async session's bind
    bind = session.get_bind()

    # For AsyncEngine, we need to access the sync_engine attribute
    # For regular Engine (in some test scenarios), use it directly
    if hasattr(bind, "sync_engine"):
        engine = bind.sync_engine
    else:
        engine = bind

    # Register the event listener
    event.listen(engine, "before_cursor_execute", _count_query)

    try:
        yield
    finally:
        # Remove the event listener
        event.remove(engine, "before_cursor_execute", _count_query)

        # Assert the query count
        if query_count != expected:
            msg = f"Expected {expected} queries, but {query_count} were executed"
            raise AssertionError(msg)
