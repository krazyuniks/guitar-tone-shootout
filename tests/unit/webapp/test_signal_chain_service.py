"""Unit tests for SignalChainService."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from gts.domain.entities.signal_chain import SignalChain as SignalChainEntity
from gts.domain.entities.signal_chain import SignalChainBlock as BlockEntity
from gts.domain.value_objects.signal_chain_enums import GearType, Platform
from webapp.adapters.persistence.models.user import User
from webapp.services.signal_chain_service import (
    SignalChainService,
    ValidationException,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_user(session: AsyncSession) -> User:
    """Create test user."""
    _sfx = uuid4().hex[:8]
    user = User(username=f"testuser_{_sfx}", email=f"test_{_sfx}@example.com")
    session.add(user)
    await session.commit()
    return user


@pytest.fixture
def service(session: AsyncSession) -> SignalChainService:
    """Create SignalChainService instance."""
    return SignalChainService(session)


class TestSignalChainServiceCreate:
    """Tests for SignalChainService.create()."""

    async def test_create_valid_chain(
        self,
        service: SignalChainService,
        test_user: User,
        session: AsyncSession,
    ) -> None:
        """Test creating a valid signal chain."""
        # Arrange
        chain_id = uuid4()
        block_id = uuid4()
        user_gear_id = uuid4()

        chain = SignalChainEntity(
            id=chain_id,
            user_id=test_user.id,
            name="My Test Chain",
            description="A valid test chain",
            platform=Platform.NAM,
            blocks=[
                BlockEntity(
                    id=block_id,
                    signal_chain_id=chain_id,
                    position=0,
                    user_gear_id=user_gear_id,
                    gear_type=GearType.FULL_RIG,
                )
            ],
        )

        # Act
        created = await service.create(chain)

        # Assert
        assert created is not None
        assert created.id == chain_id
        assert created.name == "My Test Chain"
        assert created.user_id == test_user.id
        assert len(created.blocks) == 1

    async def test_create_invalid_chain_raises_validation_error(
        self,
        service: SignalChainService,
        test_user: User,
    ) -> None:
        """Test that creating an invalid chain raises ValidationException."""
        # Arrange - chain with pedal only (no amp)
        chain = SignalChainEntity(
            id=uuid4(),
            user_id=test_user.id,
            name="Invalid Chain",
            platform=Platform.NAM,
            blocks=[
                BlockEntity(
                    id=uuid4(),
                    signal_chain_id=uuid4(),
                    position=0,
                    user_gear_id=uuid4(),
                    gear_type=GearType.PEDAL,  # No amp!
                )
            ],
        )

        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            await service.create(chain)

        assert "NO_AMP" in str(exc_info.value)

    async def test_create_commits_transaction(
        self,
        service: SignalChainService,
        test_user: User,
        session: AsyncSession,
    ) -> None:
        """Test that create commits the transaction."""
        # Arrange
        chain = SignalChainEntity(
            id=uuid4(),
            user_id=test_user.id,
            name="Test Chain",
            platform=Platform.NAM,
            blocks=[
                BlockEntity(
                    id=uuid4(),
                    signal_chain_id=uuid4(),
                    position=0,
                    user_gear_id=uuid4(),
                    gear_type=GearType.FULL_RIG,
                )
            ],
        )

        # Act
        created = await service.create(chain)

        # Expire to force fresh load
        session.expire_all()

        # Assert - verify persisted by re-querying
        result = await service.get_by_id(created.id)
        assert result is not None
        assert result.id == created.id


class TestSignalChainServiceGetById:
    """Tests for SignalChainService.get_by_id()."""

    async def test_get_existing_chain(
        self,
        service: SignalChainService,
        test_user: User,
    ) -> None:
        """Test getting an existing chain by ID."""
        # Arrange - create chain first
        chain = SignalChainEntity(
            id=uuid4(),
            user_id=test_user.id,
            name="Test Chain",
            platform=Platform.NAM,
            blocks=[
                BlockEntity(
                    id=uuid4(),
                    signal_chain_id=uuid4(),
                    position=0,
                    user_gear_id=uuid4(),
                    gear_type=GearType.FULL_RIG,
                )
            ],
        )
        created = await service.create(chain)

        # Act
        result = await service.get_by_id(created.id)

        # Assert
        assert result is not None
        assert result.id == created.id
        assert result.name == "Test Chain"

    async def test_get_nonexistent_chain_returns_none(
        self,
        service: SignalChainService,
    ) -> None:
        """Test getting a nonexistent chain returns None."""
        # Act
        result = await service.get_by_id(uuid4())

        # Assert
        assert result is None


class TestSignalChainServiceGetByUserId:
    """Tests for SignalChainService.get_by_user_id()."""

    async def test_get_user_chains(
        self,
        service: SignalChainService,
        test_user: User,
    ) -> None:
        """Test getting chains for a specific user."""
        # Arrange - create 2 chains
        for i in range(2):
            chain = SignalChainEntity(
                id=uuid4(),
                user_id=test_user.id,
                name=f"Chain {i}",
                platform=Platform.NAM,
                blocks=[
                    BlockEntity(
                        id=uuid4(),
                        signal_chain_id=uuid4(),
                        position=0,
                        user_gear_id=uuid4(),
                        gear_type=GearType.FULL_RIG,
                    )
                ],
            )
            await service.create(chain)

        # Act
        chains = await service.get_by_user_id(test_user.id)

        # Assert
        assert len(chains) == 2


class TestSignalChainServiceUpdate:
    """Tests for SignalChainService.update()."""

    async def test_update_chain_name(
        self,
        service: SignalChainService,
        test_user: User,
        session: AsyncSession,
    ) -> None:
        """Test updating a chain's name."""
        # Arrange - create chain
        chain = SignalChainEntity(
            id=uuid4(),
            user_id=test_user.id,
            name="Original Name",
            platform=Platform.NAM,
            blocks=[
                BlockEntity(
                    id=uuid4(),
                    signal_chain_id=uuid4(),
                    position=0,
                    user_gear_id=uuid4(),
                    gear_type=GearType.FULL_RIG,
                )
            ],
        )
        created = await service.create(chain)

        # Act - update name
        updated_chain = SignalChainEntity(
            id=created.id,
            user_id=created.user_id,
            name="Updated Name",
            platform=created.platform,
            blocks=created.blocks,
            created_at=created.created_at,
            updated_at=created.updated_at,
        )
        result = await service.update(updated_chain)

        # Expire to force fresh load
        session.expire_all()

        # Assert
        assert result is not None
        assert result.name == "Updated Name"

    async def test_update_invalid_chain_raises_validation_error(
        self,
        service: SignalChainService,
        test_user: User,
    ) -> None:
        """Test updating to invalid state raises ValidationException."""
        # Arrange - create valid chain
        chain = SignalChainEntity(
            id=uuid4(),
            user_id=test_user.id,
            name="Valid Chain",
            platform=Platform.NAM,
            blocks=[
                BlockEntity(
                    id=uuid4(),
                    signal_chain_id=uuid4(),
                    position=0,
                    user_gear_id=uuid4(),
                    gear_type=GearType.FULL_RIG,
                )
            ],
        )
        created = await service.create(chain)

        # Act - update to invalid state (remove amp block)
        invalid_chain = SignalChainEntity(
            id=created.id,
            user_id=created.user_id,
            name=created.name,
            platform=created.platform,
            blocks=[],  # Empty = invalid
            created_at=created.created_at,
            updated_at=created.updated_at,
        )

        # Assert
        with pytest.raises(ValidationException):
            await service.update(invalid_chain)


class TestSignalChainServiceDelete:
    """Tests for SignalChainService.delete()."""

    async def test_delete_existing_chain(
        self,
        service: SignalChainService,
        test_user: User,
    ) -> None:
        """Test deleting an existing chain."""
        # Arrange - create chain
        chain = SignalChainEntity(
            id=uuid4(),
            user_id=test_user.id,
            name="Chain to Delete",
            platform=Platform.NAM,
            blocks=[
                BlockEntity(
                    id=uuid4(),
                    signal_chain_id=uuid4(),
                    position=0,
                    user_gear_id=uuid4(),
                    gear_type=GearType.FULL_RIG,
                )
            ],
        )
        created = await service.create(chain)

        # Act
        await service.delete(created.id)

        # Assert - chain should be gone
        result = await service.get_by_id(created.id)
        assert result is None

    async def test_delete_nonexistent_chain_does_not_raise(
        self,
        service: SignalChainService,
    ) -> None:
        """Test deleting nonexistent chain doesn't raise error."""
        # Act & Assert - should not raise
        await service.delete(uuid4())
