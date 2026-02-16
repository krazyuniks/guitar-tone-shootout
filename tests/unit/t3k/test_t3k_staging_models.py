"""Unit tests for T3K staging ORM models.

Tests domain conversion (from_domain / to_domain) without database access.
Database-backed tests live in tests/integration/.
"""

from datetime import UTC, datetime

from source_t3k.adapters.outbound.models import (
    T3KModelStaging,
    T3KToneStaging,
    T3KUserStaging,
)
from source_t3k.domain.entities import T3KModel, T3KTone, T3KUser
from source_t3k.domain.value_objects import T3KGearKind, T3KPlatform


class TestT3KUserStagingConversion:
    def test_from_domain(self) -> None:
        user = T3KUser(
            id="user-abc",
            username="testuser",
            avatar_url="https://t3k.com/avatar.jpg",
            bio="Guitarist",
            url="https://t3k.com/users/testuser",
        )
        staging = T3KUserStaging.from_domain(user)

        assert staging.id == "user-abc"
        assert staging.username == "testuser"
        assert staging.avatar_url == "https://t3k.com/avatar.jpg"
        assert staging.bio == "Guitarist"
        assert staging.url == "https://t3k.com/users/testuser"

    def test_to_domain(self) -> None:
        staging = T3KUserStaging(
            id="user-abc",
            username="testuser",
            avatar_url="https://t3k.com/avatar.jpg",
            bio="Guitarist",
            url="https://t3k.com/users/testuser",
        )
        user = staging.to_domain()

        assert isinstance(user, T3KUser)
        assert user.id == "user-abc"
        assert user.username == "testuser"


class TestT3KToneStagingConversion:
    def test_from_domain(self) -> None:
        now = datetime.now(UTC)
        tone = T3KTone(
            id=42,
            title="Awesome Amp",
            description="A killer tone",
            tags=["high-gain"],
            makes=["Fender"],
            gear=T3KGearKind.AMP,
            platform=T3KPlatform.NAM,
            models_count=3,
            favorites_count=10,
            downloads_count=100,
            images=["https://t3k.com/img.jpg"],
            user_id="user-abc",
            user=None,
            url="https://t3k.com/tones/42",
            created_at=now,
            updated_at=now,
        )
        staging = T3KToneStaging.from_domain(tone)

        assert staging.id == 42
        assert staging.title == "Awesome Amp"
        assert staging.gear == "amp"
        assert staging.platform == "nam"
        assert staging.tags == ["high-gain"]
        assert staging.images == ["https://t3k.com/img.jpg"]
        assert staging.user_id == "user-abc"

    def test_to_domain(self) -> None:
        now = datetime.now(UTC)
        staging = T3KToneStaging(
            id=42,
            title="Awesome Amp",
            description="desc",
            tags=["tag1"],
            makes=["Fender"],
            gear="amp",
            platform="nam",
            models_count=3,
            favorites_count=10,
            downloads_count=100,
            images=["img.jpg"],
            user_id="user-abc",
            url="url",
            created_at=now,
            updated_at=now,
        )
        tone = staging.to_domain()

        assert isinstance(tone, T3KTone)
        assert tone.id == 42
        assert tone.gear == T3KGearKind.AMP
        assert tone.platform == T3KPlatform.NAM
        assert tone.user is None  # to_domain doesn't hydrate user

    def test_full_rig_gear_kind_roundtrip(self) -> None:
        now = datetime.now(UTC)
        tone = T3KTone(
            id=1,
            title="T",
            description="",
            tags=[],
            makes=[],
            gear=T3KGearKind.FULL_RIG,
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
        staging = T3KToneStaging.from_domain(tone)
        assert staging.gear == "full-rig"

        roundtripped = staging.to_domain()
        assert roundtripped.gear == T3KGearKind.FULL_RIG


class TestT3KModelStagingConversion:
    def test_from_domain(self) -> None:
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
        staging = T3KModelStaging.from_domain(model)

        assert staging.id == 99
        assert staging.tone_id == 42
        assert staging.name == "Clean Channel"
        assert staging.model_url == "https://t3k.com/models/99/clean.nam"
        assert staging.size == "standard"

    def test_to_domain(self) -> None:
        now = datetime.now(UTC)
        staging = T3KModelStaging(
            id=99,
            tone_id=42,
            user_id="user-abc",
            name="Clean Channel",
            model_url="https://t3k.com/models/99/clean.nam",
            size="standard",
            created_at=now,
            updated_at=now,
        )
        model = staging.to_domain()

        assert isinstance(model, T3KModel)
        assert model.id == 99
        assert model.tone_id == 42
        assert model.model_url == "https://t3k.com/models/99/clean.nam"
