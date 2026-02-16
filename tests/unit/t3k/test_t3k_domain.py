"""Unit tests for T3K domain entities and value objects."""

from datetime import UTC, datetime

import pytest

from source_t3k.domain.entities import T3KModel, T3KTone, T3KUser
from source_t3k.domain.value_objects import T3KGearKind, T3KPlatform


class TestT3KPlatform:
    """Test T3KPlatform enum."""

    def test_platform_values(self) -> None:
        assert T3KPlatform.NAM.value == "nam"
        assert T3KPlatform.AIDA_X.value == "aida-x"
        assert T3KPlatform.IR.value == "ir"


class TestT3KGearKind:
    """Test T3KGearKind enum."""

    def test_gear_kind_values(self) -> None:
        assert T3KGearKind.AMP.value == "amp"
        assert T3KGearKind.PEDAL.value == "pedal"
        assert T3KGearKind.FULL_RIG.value == "full-rig"
        assert T3KGearKind.OUTBOARD.value == "outboard"
        assert T3KGearKind.IR.value == "ir"


class TestT3KUser:
    """Test T3KUser dataclass."""

    def test_user_creation(self) -> None:
        user = T3KUser(
            id="user-abc",
            username="testuser",
            avatar_url="https://t3k.com/avatar.jpg",
            bio="A cool guitarist",
            url="https://t3k.com/users/testuser",
        )

        assert user.id == "user-abc"
        assert user.username == "testuser"
        assert user.bio == "A cool guitarist"

    def test_user_is_frozen(self) -> None:
        user = T3KUser(id="u1", username="u", avatar_url="", bio="", url="")
        with pytest.raises(AttributeError):
            user.username = "new"  # type: ignore[misc]

    def test_user_has_slots(self) -> None:
        user = T3KUser(id="u1", username="u", avatar_url="", bio="", url="")
        assert hasattr(T3KUser, "__slots__")
        with pytest.raises(AttributeError):
            _ = user.__dict__  # type: ignore[misc]


class TestT3KTone:
    """Test T3KTone dataclass."""

    def test_tone_creation(self) -> None:
        now = datetime.now(UTC)
        tone = T3KTone(
            id=42,
            title="Awesome Amp",
            description="A killer tone",
            tags=["high-gain", "metal"],
            makes=["Fender"],
            gear=T3KGearKind.AMP,
            platform=T3KPlatform.NAM,
            models_count=3,
            favorites_count=10,
            downloads_count=100,
            images=["https://t3k.com/img1.jpg"],
            user_id="user-abc",
            user=None,
            url="https://t3k.com/tones/42",
            created_at=now,
            updated_at=now,
        )

        assert tone.id == 42
        assert tone.title == "Awesome Amp"
        assert tone.tags == ["high-gain", "metal"]
        assert tone.gear == T3KGearKind.AMP
        assert tone.platform == T3KPlatform.NAM

    def test_tone_is_frozen(self) -> None:
        now = datetime.now(UTC)
        tone = T3KTone(
            id=1,
            title="T",
            description="",
            tags=[],
            makes=[],
            gear=T3KGearKind.AMP,
            platform=T3KPlatform.NAM,
            models_count=0,
            favorites_count=0,
            downloads_count=0,
            images=[],
            user_id="u",
            user=None,
            url="",
            created_at=now,
            updated_at=now,
        )
        with pytest.raises(AttributeError):
            tone.title = "New"  # type: ignore[misc]


class TestT3KModel:
    """Test T3KModel dataclass."""

    def test_model_creation(self) -> None:
        now = datetime.now(UTC)
        model = T3KModel(
            id=99,
            tone_id=42,
            user_id="user-abc",
            name="Clean Channel",
            model_url="https://t3k.com/models/99/clean.nam",
            size="standard",
            created_at=now,
            updated_at=now,
        )

        assert model.id == 99
        assert model.tone_id == 42
        assert model.model_url == "https://t3k.com/models/99/clean.nam"

    def test_model_is_frozen(self) -> None:
        now = datetime.now(UTC)
        model = T3KModel(
            id=1,
            tone_id=1,
            user_id="u",
            name="m",
            model_url="url",
            size="standard",
            created_at=now,
            updated_at=now,
        )
        with pytest.raises(AttributeError):
            model.name = "New"  # type: ignore[misc]


class TestT3KDomainIntegration:
    """Integration tests for T3K domain entities working together."""

    def test_tone_and_user_relationship(self) -> None:
        user = T3KUser(id="user-abc", username="testuser", avatar_url="", bio="", url="")
        now = datetime.now(UTC)
        tone = T3KTone(
            id=42,
            title="T",
            description="",
            tags=[],
            makes=[],
            gear=T3KGearKind.AMP,
            platform=T3KPlatform.NAM,
            models_count=0,
            favorites_count=0,
            downloads_count=0,
            images=[],
            user_id=user.id,
            user=user,
            url="",
            created_at=now,
            updated_at=now,
        )

        assert tone.user_id == user.id
        assert tone.user is user

    def test_model_and_tone_relationship(self) -> None:
        now = datetime.now(UTC)
        model = T3KModel(
            id=99,
            tone_id=42,
            user_id="u",
            name="m",
            model_url="url",
            size="standard",
            created_at=now,
            updated_at=now,
        )

        assert model.tone_id == 42
