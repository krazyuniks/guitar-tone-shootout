"""Unit tests for SignalChain Pydantic schemas."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from webapp.api.v1.schemas.signal_chain import (
    BlockRequest,
    SignalChainCreateRequest,
    SignalChainResponse,
    SignalChainUpdateRequest,
)


class TestBlockRequest:
    """Tests for BlockRequest schema."""

    def test_valid_block_request(self) -> None:
        """Test creating valid block request."""
        # Act
        block = BlockRequest(
            user_gear_id=uuid4(),
            gear_type="amp",
            position=0,
        )

        # Assert
        assert block.user_gear_id is not None
        assert block.gear_type == "amp"
        assert block.position == 0

    def test_block_request_requires_user_gear_id(self) -> None:
        """Test that user_gear_id is required."""
        # Act & Assert
        with pytest.raises(ValidationError):
            BlockRequest(
                gear_type="amp",
                position=0,
            )

    def test_block_request_requires_gear_type(self) -> None:
        """Test that gear_type is required."""
        # Act & Assert
        with pytest.raises(ValidationError):
            BlockRequest(
                user_gear_id=uuid4(),
                position=0,
            )

    def test_block_request_requires_position(self) -> None:
        """Test that position is required."""
        # Act & Assert
        with pytest.raises(ValidationError):
            BlockRequest(
                user_gear_id=uuid4(),
                gear_type="amp",
            )


class TestSignalChainCreateRequest:
    """Tests for SignalChainCreateRequest schema."""

    def test_valid_create_request(self) -> None:
        """Test creating valid chain create request."""
        # Act
        request = SignalChainCreateRequest(
            name="Test Chain",
            platform="nam",
            description="A test chain",
            blocks=[
                BlockRequest(
                    user_gear_id=uuid4(),
                    gear_type="full_rig",
                    position=0,
                )
            ],
        )

        # Assert
        assert request.name == "Test Chain"
        assert request.platform == "nam"
        assert request.description == "A test chain"
        assert len(request.blocks) == 1

    def test_create_request_requires_name(self) -> None:
        """Test that name is required."""
        # Act & Assert
        with pytest.raises(ValidationError):
            SignalChainCreateRequest(
                platform="nam",
                blocks=[],
            )

    def test_create_request_requires_platform(self) -> None:
        """Test that platform is required."""
        # Act & Assert
        with pytest.raises(ValidationError):
            SignalChainCreateRequest(
                name="Test",
                blocks=[],
            )

    def test_create_request_requires_blocks(self) -> None:
        """Test that blocks is required."""
        # Act & Assert
        with pytest.raises(ValidationError):
            SignalChainCreateRequest(
                name="Test",
                platform="nam",
            )

    def test_create_request_description_optional(self) -> None:
        """Test that description is optional."""
        # Act
        request = SignalChainCreateRequest(
            name="Test",
            platform="nam",
            blocks=[],
        )

        # Assert
        assert request.description is None


class TestSignalChainUpdateRequest:
    """Tests for SignalChainUpdateRequest schema."""

    def test_valid_update_request(self) -> None:
        """Test creating valid chain update request."""
        # Act
        request = SignalChainUpdateRequest(
            name="Updated Chain",
            platform="nam",
            blocks=[
                BlockRequest(
                    user_gear_id=uuid4(),
                    gear_type="full_rig",
                    position=0,
                )
            ],
        )

        # Assert
        assert request.name == "Updated Chain"
        assert request.platform == "nam"
        assert len(request.blocks) == 1

    def test_update_request_requires_name(self) -> None:
        """Test that name is required."""
        # Act & Assert
        with pytest.raises(ValidationError):
            SignalChainUpdateRequest(
                platform="nam",
                blocks=[],
            )


class TestSignalChainResponse:
    """Tests for SignalChainResponse schema."""

    def test_response_from_attributes(self) -> None:
        """Test that response schema works with from_attributes."""
        # Arrange - mock entity-like object
        class MockBlock:
            id = uuid4()
            user_gear_id = uuid4()
            gear_type = "amp"
            position = 0

        class MockChain:
            id = uuid4()
            user_id = uuid4()
            name = "Test Chain"
            description = "Test"
            platform = "nam"
            blocks = [MockBlock()]
            created_at = "2024-01-01T00:00:00"
            updated_at = "2024-01-01T00:00:00"

        # Act
        response = SignalChainResponse.model_validate(MockChain())

        # Assert
        assert response.id == MockChain.id
        assert response.name == "Test Chain"
        assert len(response.blocks) == 1

    def test_response_has_config_from_attributes(self) -> None:
        """Test that response schema has from_attributes config."""
        # Assert
        assert SignalChainResponse.model_config.get("from_attributes") is True
