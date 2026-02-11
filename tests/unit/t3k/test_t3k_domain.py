"""Unit tests for T3K domain entities and value objects."""

from datetime import UTC, datetime

import pytest

from source_t3k.domain.entities import T3KCreator, T3KModel, T3KPack
from source_t3k.domain.value_objects import T3KPackType, T3KPlatform


class TestT3KPlatform:
    """Test T3KPlatform enum."""

    def test_platform_has_nam_value(self) -> None:
        """T3KPlatform should have NAM platform."""
        assert T3KPlatform.NAM.value == "nam"

    def test_platform_has_aida_x_value(self) -> None:
        """T3KPlatform should have AIDA-X platform."""
        assert T3KPlatform.AIDA_X.value == "aida_x"

    def test_platform_has_ir_value(self) -> None:
        """T3KPlatform should have IR platform."""
        assert T3KPlatform.IR.value == "ir"


class TestT3KPackType:
    """Test T3KPackType enum."""

    def test_pack_type_has_amp_value(self) -> None:
        """T3KPackType should have amp pack type."""
        assert T3KPackType.AMP.value == "amp"

    def test_pack_type_has_pedal_value(self) -> None:
        """T3KPackType should have pedal pack type."""
        assert T3KPackType.PEDAL.value == "pedal"

    def test_pack_type_has_ir_value(self) -> None:
        """T3KPackType should have IR pack type."""
        assert T3KPackType.IR.value == "ir"


class TestT3KCreator:
    """Test T3KCreator dataclass."""

    def test_creator_creation_with_required_fields(self) -> None:
        """T3KCreator should be creatable with required fields."""
        creator_id = "creator-123"
        username = "testuser"
        display_name = "Test User"
        avatar_url = "https://t3k.com/avatar.jpg"
        profile_url = "https://t3k.com/profile/testuser"

        creator = T3KCreator(
            id=creator_id,
            username=username,
            display_name=display_name,
            avatar_url=avatar_url,
            profile_url=profile_url,
        )

        assert creator.id == creator_id
        assert creator.username == username
        assert creator.display_name == display_name
        assert creator.avatar_url == avatar_url
        assert creator.profile_url == profile_url

    def test_creator_is_frozen(self) -> None:
        """T3KCreator should be frozen (immutable)."""
        creator = T3KCreator(
            id="creator-123",
            username="testuser",
            display_name="Test User",
            avatar_url="https://t3k.com/avatar.jpg",
            profile_url="https://t3k.com/profile/testuser",
        )

        with pytest.raises(AttributeError):
            creator.username = "newuser"  # type: ignore[misc]

    def test_creator_has_slots(self) -> None:
        """T3KCreator should use __slots__ for memory efficiency."""
        creator = T3KCreator(
            id="creator-123",
            username="testuser",
            display_name="Test User",
            avatar_url="https://t3k.com/avatar.jpg",
            profile_url="https://t3k.com/profile/testuser",
        )

        assert hasattr(T3KCreator, "__slots__")
        with pytest.raises(AttributeError):
            _ = creator.__dict__  # type: ignore[misc]


class TestT3KPack:
    """Test T3KPack dataclass."""

    def test_pack_creation_with_required_fields(self) -> None:
        """T3KPack should be creatable with required fields."""
        pack_id = "pack-456"
        name = "Test Pack"
        slug = "test-pack"
        creator_id = "creator-123"
        description = "A test pack description"
        thumbnail_url = "https://t3k.com/thumb.jpg"
        platform = T3KPlatform.NAM
        pack_type = T3KPackType.AMP
        created_at = datetime.now(UTC)
        updated_at = datetime.now(UTC)

        pack = T3KPack(
            id=pack_id,
            name=name,
            slug=slug,
            creator_id=creator_id,
            description=description,
            thumbnail_url=thumbnail_url,
            platform=platform,
            pack_type=pack_type,
            created_at=created_at,
            updated_at=updated_at,
        )

        assert pack.id == pack_id
        assert pack.name == name
        assert pack.slug == slug
        assert pack.creator_id == creator_id
        assert pack.description == description
        assert pack.thumbnail_url == thumbnail_url
        assert pack.platform == platform
        assert pack.pack_type == pack_type
        assert pack.created_at == created_at
        assert pack.updated_at == updated_at

    def test_pack_is_frozen(self) -> None:
        """T3KPack should be frozen (immutable)."""
        pack = T3KPack(
            id="pack-456",
            name="Test Pack",
            slug="test-pack",
            creator_id="creator-123",
            description="A test pack",
            thumbnail_url="https://t3k.com/thumb.jpg",
            platform=T3KPlatform.NAM,
            pack_type=T3KPackType.AMP,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        with pytest.raises(AttributeError):
            pack.name = "New Name"  # type: ignore[misc]

    def test_pack_has_slots(self) -> None:
        """T3KPack should use __slots__ for memory efficiency."""
        pack = T3KPack(
            id="pack-456",
            name="Test Pack",
            slug="test-pack",
            creator_id="creator-123",
            description="A test pack",
            thumbnail_url="https://t3k.com/thumb.jpg",
            platform=T3KPlatform.NAM,
            pack_type=T3KPackType.AMP,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert hasattr(T3KPack, "__slots__")
        with pytest.raises(AttributeError):
            _ = pack.__dict__  # type: ignore[misc]


class TestT3KModel:
    """Test T3KModel dataclass."""

    def test_model_creation_with_required_fields(self) -> None:
        """T3KModel should be creatable with required fields."""
        model_id = "model-789"
        pack_id = "pack-456"
        name = "Test Model"
        filename = "test-model.nam"
        file_size = 1024000
        download_url = "https://t3k.com/download/model.nam"
        checksum = "abc123def456"
        created_at = datetime.now(UTC)
        updated_at = datetime.now(UTC)

        model = T3KModel(
            id=model_id,
            pack_id=pack_id,
            name=name,
            filename=filename,
            file_size=file_size,
            download_url=download_url,
            checksum=checksum,
            created_at=created_at,
            updated_at=updated_at,
        )

        assert model.id == model_id
        assert model.pack_id == pack_id
        assert model.name == name
        assert model.filename == filename
        assert model.file_size == file_size
        assert model.download_url == download_url
        assert model.checksum == checksum
        assert model.created_at == created_at
        assert model.updated_at == updated_at

    def test_model_is_frozen(self) -> None:
        """T3KModel should be frozen (immutable)."""
        model = T3KModel(
            id="model-789",
            pack_id="pack-456",
            name="Test Model",
            filename="test-model.nam",
            file_size=1024000,
            download_url="https://t3k.com/download/model.nam",
            checksum="abc123",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        with pytest.raises(AttributeError):
            model.name = "New Name"  # type: ignore[misc]

    def test_model_has_slots(self) -> None:
        """T3KModel should use __slots__ for memory efficiency."""
        model = T3KModel(
            id="model-789",
            pack_id="pack-456",
            name="Test Model",
            filename="test-model.nam",
            file_size=1024000,
            download_url="https://t3k.com/download/model.nam",
            checksum="abc123",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert hasattr(T3KModel, "__slots__")
        with pytest.raises(AttributeError):
            _ = model.__dict__  # type: ignore[misc]


class TestT3KDomainIntegration:
    """Integration tests for T3K domain entities working together."""

    def test_pack_and_creator_relationship(self) -> None:
        """T3KPack should reference T3KCreator via creator_id."""
        creator = T3KCreator(
            id="creator-123",
            username="testuser",
            display_name="Test User",
            avatar_url="https://t3k.com/avatar.jpg",
            profile_url="https://t3k.com/profile/testuser",
        )

        pack = T3KPack(
            id="pack-456",
            name="Test Pack",
            slug="test-pack",
            creator_id=creator.id,
            description="A test pack",
            thumbnail_url="https://t3k.com/thumb.jpg",
            platform=T3KPlatform.NAM,
            pack_type=T3KPackType.AMP,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert pack.creator_id == creator.id

    def test_model_and_pack_relationship(self) -> None:
        """T3KModel should reference T3KPack via pack_id."""
        pack = T3KPack(
            id="pack-456",
            name="Test Pack",
            slug="test-pack",
            creator_id="creator-123",
            description="A test pack",
            thumbnail_url="https://t3k.com/thumb.jpg",
            platform=T3KPlatform.NAM,
            pack_type=T3KPackType.AMP,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        model = T3KModel(
            id="model-789",
            pack_id=pack.id,
            name="Test Model",
            filename="test-model.nam",
            file_size=1024000,
            download_url="https://t3k.com/download/model.nam",
            checksum="abc123",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert model.pack_id == pack.id
