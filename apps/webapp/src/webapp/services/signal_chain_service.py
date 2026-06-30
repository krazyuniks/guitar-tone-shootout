"""SignalChainService for managing signal chains with validation."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from gts.domain.entities.signal_chain import SignalChain
from gts.services.signal_chain_validator import SignalChainValidator
from webapp.adapters.persistence.repositories.signal_chain_repository import (
    SQLAlchemySignalChainRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ValidationException(Exception):
    """Exception raised when signal chain validation fails."""

    def __init__(self, errors: list[str]) -> None:
        """Initialize validation exception with error messages.

        Args:
            errors: List of validation error messages
        """
        self.errors = errors
        super().__init__(f"Validation failed: {', '.join(errors)}")


class SignalChainService:
    """Service for managing signal chains with validation.

    Handles CRUD operations for signal chains, delegating validation
    to SignalChainValidator and persistence to SignalChainRepository.

    Transaction management is the caller's responsibility.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize service with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.repository = SQLAlchemySignalChainRepository(session)
        self.validator = SignalChainValidator()

    async def create(self, chain: SignalChain) -> SignalChain:
        """Create a new signal chain.

        Validates the chain before persisting.

        Args:
            chain: SignalChain entity to create

        Returns:
            The created SignalChain entity

        Raises:
            ValidationException: If chain validation fails
        """
        # Validate chain
        result = self.validator.validate(chain)
        if not result.is_valid:
            error_messages = [f"{error.code}: {error.message}" for error in result.errors]
            raise ValidationException(error_messages)

        # Persist chain (transaction managed by caller)
        await self.repository.save(chain)
        await self.session.flush()

        return chain

    async def get_by_id(self, chain_id: UUID, user_id: UUID) -> SignalChain | None:
        """Get a signal chain by ID, scoped to the owning user.

        Args:
            chain_id: Chain ID to retrieve
            user_id: The requesting user's UUID — filters at the query level

        Returns:
            SignalChain entity if found and owned, None otherwise
        """
        return await self.repository.get_by_id(chain_id, user_id)

    async def get_by_user_id(
        self, user_id: UUID, limit: int | None = None, offset: int = 0
    ) -> list[SignalChain]:
        """Get all signal chains for a user.

        Args:
            user_id: User ID to filter by
            limit: Maximum number of chains to return
            offset: Number of chains to skip

        Returns:
            List of SignalChain entities
        """
        return await self.repository.get_by_user_id(user_id, limit=limit or 50, offset=offset)

    async def update(self, chain: SignalChain) -> SignalChain:
        """Update an existing signal chain.

        Validates the chain before persisting.

        Args:
            chain: SignalChain entity to update

        Returns:
            The updated SignalChain entity

        Raises:
            ValidationException: If chain validation fails
        """
        # Validate chain
        result = self.validator.validate(chain)
        if not result.is_valid:
            error_messages = [f"{error.code}: {error.message}" for error in result.errors]
            raise ValidationException(error_messages)

        # Persist chain (transaction managed by caller)
        await self.repository.save(chain)
        await self.session.flush()

        return chain

    async def delete(self, chain_id: UUID) -> None:
        """Delete a signal chain.

        Args:
            chain_id: ID of chain to delete
        """
        # Delete chain (transaction managed by caller)
        await self.repository.delete(chain_id)
        await self.session.flush()
