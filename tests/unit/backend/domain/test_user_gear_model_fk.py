"""Unit tests for UserGear domain entity FK to GearModel."""

from uuid import UUID, uuid4

from gts.domain.entities.gear import UserGear


class TestUserGearDomainModelFK:
    """Test UserGear entity has gear_model_id instead of gear_id."""

    def test_user_gear_has_gear_model_id_field(self) -> None:
        """UserGear domain entity should have gear_model_id field."""
        user_id = uuid4()
        gear_model_id = uuid4()

        user_gear = UserGear(
            user_id=user_id,
            gear_model_id=gear_model_id,
        )

        assert hasattr(user_gear, "gear_model_id")
        assert user_gear.gear_model_id == gear_model_id

    def test_user_gear_does_not_have_gear_id_field(self) -> None:
        """UserGear domain entity should NOT have gear_id field."""
        user_gear = UserGear(
            user_id=uuid4(),
            gear_model_id=uuid4(),
        )

        # Should not have gear_id attribute
        assert not hasattr(user_gear, "gear_id")

    def test_user_gear_gear_model_id_is_uuid(self) -> None:
        """gear_model_id should accept UUID values."""
        user_id = uuid4()
        gear_model_id = uuid4()

        user_gear = UserGear(
            user_id=user_id,
            gear_model_id=gear_model_id,
        )

        assert isinstance(user_gear.gear_model_id, UUID)
        assert user_gear.gear_model_id == gear_model_id
