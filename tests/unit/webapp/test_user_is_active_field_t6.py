"""Unit tests for User ORM model is_active field - Task T6.

This task adds the is_active field to the existing User ORM model.
The User model already exists but is missing the is_active field from the domain model.

Tests verify:
- is_active field exists and is a boolean
- is_active defaults to True
- is_active can be explicitly set to False
- is_active is stored in the database correctly
"""

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.user import User


@pytest.fixture
async def db_session() -> AsyncSession:
    """Create an in-memory SQLite session for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = async_session()

    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


def test_user_model_has_is_active_column() -> None:
    """User model must have is_active column in the table schema."""
    # Get the table columns via SQLAlchemy inspection
    inspector = inspect(User)
    column_names = {col.key for col in inspector.columns}

    # This will fail with AssertionError (not TypeError) if column doesn't exist
    assert "is_active" in column_names, (
        "User model is missing is_active field. "
        "Domain model defines is_active: bool = True (line 52 of libs/core/src/core/domain/entities/user.py). "
        "ORM model must have matching field."
    )


def test_user_model_is_active_column_is_boolean() -> None:
    """User model is_active column must be Boolean type."""
    inspector = inspect(User)

    # Find the is_active column
    is_active_col = None
    for col in inspector.columns:
        if col.key == "is_active":
            is_active_col = col
            break

    # This will fail if column doesn't exist
    assert is_active_col is not None, "is_active column not found in User model"

    # Check the SQL type - should be Boolean
    # We check the Python type that SQLAlchemy expects
    assert hasattr(is_active_col, "type"), "Column has no type attribute"
    # SQLAlchemy Boolean type will have __visit_name__ == 'boolean'
    assert hasattr(is_active_col.type, "__visit_name__"), "Type has no __visit_name__"
    assert is_active_col.type.__visit_name__ == "boolean", (
        f"is_active column must be Boolean type, got {is_active_col.type.__visit_name__}"
    )


def test_user_model_is_active_column_not_nullable() -> None:
    """User model is_active column must not be nullable (has default)."""
    inspector = inspect(User)

    # Find the is_active column
    is_active_col = None
    for col in inspector.columns:
        if col.key == "is_active":
            is_active_col = col
            break

    assert is_active_col is not None, "is_active column not found"

    # Column should not be nullable (has default value)
    assert is_active_col.nullable is False, (
        "is_active column should not be nullable (should have default=True)"
    )


def test_user_model_is_active_column_has_default() -> None:
    """User model is_active column must have default value of True."""
    inspector = inspect(User)

    # Find the is_active column
    is_active_col = None
    for col in inspector.columns:
        if col.key == "is_active":
            is_active_col = col
            break

    assert is_active_col is not None, "is_active column not found"

    # Check for default value
    # In SQLAlchemy, column.default might be a ColumnDefault object or None
    assert is_active_col.default is not None, (
        "is_active column must have a default value (should default to True)"
    )


@pytest.mark.asyncio
async def test_user_model_is_active_defaults_to_true(db_session: AsyncSession) -> None:
    """When creating a user without specifying is_active, it defaults to True."""
    # Create user without specifying is_active
    user = User(username="test_user")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Should have is_active=True by default
    assert hasattr(user, "is_active"), "User instance missing is_active attribute"
    assert user.is_active is True, (
        "User.is_active should default to True when not specified. "
        "Domain model has is_active: bool = True as default."
    )


@pytest.mark.asyncio
async def test_user_model_is_active_can_be_set_to_false(db_session: AsyncSession) -> None:
    """User can be created with is_active=False explicitly."""
    # Create user with is_active=False
    user = User(username="test_user", is_active=False)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert hasattr(user, "is_active"), "User instance missing is_active attribute"
    assert user.is_active is False, "is_active should be False when explicitly set"


@pytest.mark.asyncio
async def test_user_model_is_active_can_be_set_to_true(db_session: AsyncSession) -> None:
    """User can be created with is_active=True explicitly."""
    # Create user with is_active=True explicitly
    user = User(username="test_user", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.is_active is True


@pytest.mark.asyncio
async def test_user_model_is_active_persists_to_database(db_session: AsyncSession) -> None:
    """User is_active value is correctly persisted to and retrieved from database."""
    # Create an inactive user
    user = User(username="inactive_user", is_active=False)
    db_session.add(user)
    await db_session.commit()
    user_id = user.id

    # Expire all cached state to force fresh database read
    db_session.expire_all()

    # Query the user from database (forces fresh read)
    result = await db_session.execute(select(User).where(User.id == user_id))
    retrieved_user = result.scalar_one()

    # Should still be inactive
    assert retrieved_user.is_active is False, (
        "is_active value not persisted correctly to database"
    )


@pytest.mark.asyncio
async def test_user_model_is_active_can_be_updated(db_session: AsyncSession) -> None:
    """User is_active can be updated after creation."""
    # Create active user
    user = User(username="test_user", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.is_active is True

    # Deactivate user
    user.is_active = False
    await db_session.commit()
    await db_session.refresh(user)

    assert user.is_active is False

    # Reactivate user
    user.is_active = True
    await db_session.commit()
    await db_session.refresh(user)

    assert user.is_active is True
