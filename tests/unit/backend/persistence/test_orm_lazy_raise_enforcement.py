"""Unit tests verifying all ORM relationships use lazy='raise'.

These tests enforce the query pattern rule that prevents implicit N+1 queries
by requiring explicit eager loading in all repository queries.

Reference: .claude/rules/query-patterns.md:25-50
"""

import pytest
from sqlalchemy import inspect as sa_inspect

from webapp.adapters.persistence.models.block_type import BlockType
from webapp.adapters.persistence.models.gear import Gear, GearMake, GearTag
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.gear_source import GearSource
from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.preset import Preset
from webapp.adapters.persistence.models.shootout import (
    AudioSegment,
    DITrack,
    Shootout,
    ShootoutChain,
)
from webapp.adapters.persistence.models.signal_chain import (
    SignalChain,
    SignalChainBlock,
    SignalChainGroup,
)
from webapp.adapters.persistence.models.user import OAuthProvider, User
from webapp.adapters.persistence.models.user_gear import UserGear
from webapp.adapters.persistence.models.user_identity import UserIdentity


def get_relationship_lazy_strategy(model_class, relationship_name):
    """Get the lazy strategy for a specific relationship.

    Returns the lazy loading strategy ('raise', 'select', 'selectin', etc.)
    or None if the relationship doesn't exist.
    """
    mapper = sa_inspect(model_class)
    if relationship_name not in mapper.relationships:
        return None
    rel = mapper.relationships[relationship_name]
    return rel.lazy


class TestGearModelLazyRaise:
    """Test Gear model relationships use lazy='raise'."""

    def test_gear_make_relationship_uses_lazy_raise(self):
        """Gear.make relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(Gear, "make")
        assert lazy_strategy is not None, "make relationship not found"
        assert lazy_strategy == "raise", f"Gear.make has lazy={lazy_strategy}, expected 'raise'"

    def test_gear_source_relationship_uses_lazy_raise(self):
        """Gear.source relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(Gear, "source")
        assert lazy_strategy is not None, "source relationship not found"
        assert lazy_strategy == "raise", f"Gear.source has lazy={lazy_strategy}, expected 'raise'"

    def test_gear_models_relationship_uses_lazy_raise(self):
        """Gear.models relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(Gear, "models")
        assert lazy_strategy is not None, "models relationship not found"
        assert lazy_strategy == "raise", f"Gear.models has lazy={lazy_strategy}, expected 'raise'"

    def test_gear_tags_relationship_uses_lazy_raise(self):
        """Gear.tags relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(Gear, "tags")
        assert lazy_strategy is not None, "tags relationship not found"
        assert lazy_strategy == "raise", f"Gear.tags has lazy={lazy_strategy}, expected 'raise'"

    def test_gear_user_gear_relationship_uses_lazy_raise(self):
        """Gear.user_gear relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(Gear, "user_gear")
        assert lazy_strategy is not None, "user_gear relationship not found"
        assert lazy_strategy == "raise", f"Gear.user_gear has lazy={lazy_strategy}, expected 'raise'"


class TestUserModelLazyRaise:
    """Test User model relationships use lazy='raise'."""

    def test_user_identities_relationship_uses_lazy_raise(self):
        """User.identities relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(User, "identities")
        assert lazy_strategy is not None, "identities relationship not found"
        assert lazy_strategy == "raise", f"User.identities has lazy={lazy_strategy}, expected 'raise'"

    def test_user_signal_chains_relationship_uses_lazy_raise(self):
        """User.signal_chains relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(User, "signal_chains")
        assert lazy_strategy is not None, "signal_chains relationship not found"
        assert lazy_strategy == "raise", f"User.signal_chains has lazy={lazy_strategy}, expected 'raise'"

    def test_user_signal_chain_groups_relationship_uses_lazy_raise(self):
        """User.signal_chain_groups relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(User, "signal_chain_groups")
        assert lazy_strategy is not None, "signal_chain_groups relationship not found"
        assert lazy_strategy == "raise", f"User.signal_chain_groups has lazy={lazy_strategy}, expected 'raise'"

    def test_user_di_tracks_relationship_uses_lazy_raise(self):
        """User.di_tracks relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(User, "di_tracks")
        assert lazy_strategy is not None, "di_tracks relationship not found"
        assert lazy_strategy == "raise", f"User.di_tracks has lazy={lazy_strategy}, expected 'raise'"

    def test_user_shootouts_relationship_uses_lazy_raise(self):
        """User.shootouts relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(User, "shootouts")
        assert lazy_strategy is not None, "shootouts relationship not found"
        assert lazy_strategy == "raise", f"User.shootouts has lazy={lazy_strategy}, expected 'raise'"

    def test_user_jobs_relationship_uses_lazy_raise(self):
        """User.jobs relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(User, "jobs")
        assert lazy_strategy is not None, "jobs relationship not found"
        assert lazy_strategy == "raise", f"User.jobs has lazy={lazy_strategy}, expected 'raise'"

    def test_user_user_gear_relationship_uses_lazy_raise(self):
        """User.user_gear relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(User, "user_gear")
        assert lazy_strategy is not None, "user_gear relationship not found"
        assert lazy_strategy == "raise", f"User.user_gear has lazy={lazy_strategy}, expected 'raise'"


class TestSignalChainModelLazyRaise:
    """Test SignalChain model relationships use lazy='raise'."""

    def test_signal_chain_user_relationship_uses_lazy_raise(self):
        """SignalChain.user relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(SignalChain, "user")
        assert lazy_strategy is not None, "user relationship not found"
        assert lazy_strategy == "raise", f"SignalChain.user has lazy={lazy_strategy}, expected 'raise'"

    def test_signal_chain_blocks_relationship_uses_lazy_raise(self):
        """SignalChain.blocks relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(SignalChain, "blocks")
        assert lazy_strategy is not None, "blocks relationship not found"
        assert lazy_strategy == "raise", f"SignalChain.blocks has lazy={lazy_strategy}, expected 'raise'"


class TestShootoutModelLazyRaise:
    """Test Shootout model relationships use lazy='raise'."""

    def test_shootout_user_relationship_uses_lazy_raise(self):
        """Shootout.user relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(Shootout, "user")
        assert lazy_strategy is not None, "user relationship not found"
        assert lazy_strategy == "raise", f"Shootout.user has lazy={lazy_strategy}, expected 'raise'"

    def test_shootout_di_track_relationship_uses_lazy_raise(self):
        """Shootout.di_track relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(Shootout, "di_track")
        assert lazy_strategy is not None, "di_track relationship not found"
        assert lazy_strategy == "raise", f"Shootout.di_track has lazy={lazy_strategy}, expected 'raise'"

    def test_shootout_chains_relationship_uses_lazy_raise(self):
        """Shootout.chains relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(Shootout, "chains")
        assert lazy_strategy is not None, "chains relationship not found"
        assert lazy_strategy == "raise", f"Shootout.chains has lazy={lazy_strategy}, expected 'raise'"


class TestUserIdentityModelLazyRaise:
    """Test UserIdentity model relationships use lazy='raise'."""

    def test_user_identity_user_relationship_uses_lazy_raise(self):
        """UserIdentity.user relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(UserIdentity, "user")
        assert lazy_strategy is not None, "user relationship not found"
        assert lazy_strategy == "raise", f"UserIdentity.user has lazy={lazy_strategy}, expected 'raise'"

    def test_user_identity_provider_relationship_uses_lazy_raise(self):
        """UserIdentity.provider relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(UserIdentity, "provider")
        assert lazy_strategy is not None, "provider relationship not found"
        assert lazy_strategy == "raise", f"UserIdentity.provider has lazy={lazy_strategy}, expected 'raise'"


class TestOtherModelsLazyRaise:
    """Test other models' relationships use lazy='raise'."""

    def test_user_gear_user_relationship_uses_lazy_raise(self):
        """UserGear.user relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(UserGear, "user")
        assert lazy_strategy is not None, "user relationship not found"
        assert lazy_strategy == "raise", f"UserGear.user has lazy={lazy_strategy}, expected 'raise'"

    def test_user_gear_gear_relationship_uses_lazy_raise(self):
        """UserGear.gear relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(UserGear, "gear")
        assert lazy_strategy is not None, "gear relationship not found"
        assert lazy_strategy == "raise", f"UserGear.gear has lazy={lazy_strategy}, expected 'raise'"

    def test_gear_source_gear_relationship_uses_lazy_raise(self):
        """GearSource.gear relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(GearSource, "gear")
        assert lazy_strategy is not None, "gear relationship not found"
        assert lazy_strategy == "raise", f"GearSource.gear has lazy={lazy_strategy}, expected 'raise'"

    def test_job_user_relationship_already_has_lazy_raise(self):
        """Job.user relationship should already use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(Job, "user")
        assert lazy_strategy is not None, "user relationship not found"
        # This should PASS (Job already has lazy='raise')
        assert lazy_strategy == "raise", f"Job.user has lazy={lazy_strategy}, expected 'raise'"

    def test_gear_model_gear_relationship_uses_lazy_raise(self):
        """GearModel.gear relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(GearModel, "gear")
        assert lazy_strategy is not None, "gear relationship not found"
        assert lazy_strategy == "raise", f"GearModel.gear has lazy={lazy_strategy}, expected 'raise'"

    def test_oauth_provider_identities_relationship_uses_lazy_raise(self):
        """OAuthProvider.identities relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(OAuthProvider, "identities")
        assert lazy_strategy is not None, "identities relationship not found"
        assert lazy_strategy == "raise", f"OAuthProvider.identities has lazy={lazy_strategy}, expected 'raise'"

    def test_gear_make_gear_items_relationship_uses_lazy_raise(self):
        """GearMake.gear_items relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(GearMake, "gear_items")
        assert lazy_strategy is not None, "gear_items relationship not found"
        assert lazy_strategy == "raise", f"GearMake.gear_items has lazy={lazy_strategy}, expected 'raise'"

    def test_gear_tag_gear_items_relationship_uses_lazy_raise(self):
        """GearTag.gear_items relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(GearTag, "gear_items")
        assert lazy_strategy is not None, "gear_items relationship not found"
        assert lazy_strategy == "raise", f"GearTag.gear_items has lazy={lazy_strategy}, expected 'raise'"

    def test_di_track_user_relationship_uses_lazy_raise(self):
        """DITrack.user relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(DITrack, "user")
        assert lazy_strategy is not None, "user relationship not found"
        assert lazy_strategy == "raise", f"DITrack.user has lazy={lazy_strategy}, expected 'raise'"

    def test_di_track_shootouts_relationship_uses_lazy_raise(self):
        """DITrack.shootouts relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(DITrack, "shootouts")
        assert lazy_strategy is not None, "shootouts relationship not found"
        assert lazy_strategy == "raise", f"DITrack.shootouts has lazy={lazy_strategy}, expected 'raise'"

    def test_signal_chain_block_signal_chain_relationship_uses_lazy_raise(self):
        """SignalChainBlock.signal_chain relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(SignalChainBlock, "signal_chain")
        assert lazy_strategy is not None, "signal_chain relationship not found"
        assert lazy_strategy == "raise", f"SignalChainBlock.signal_chain has lazy={lazy_strategy}, expected 'raise'"

    def test_signal_chain_block_block_type_relationship_uses_lazy_raise(self):
        """SignalChainBlock.block_type relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(SignalChainBlock, "block_type")
        assert lazy_strategy is not None, "block_type relationship not found"
        assert lazy_strategy == "raise", f"SignalChainBlock.block_type has lazy={lazy_strategy}, expected 'raise'"

    def test_signal_chain_block_presets_relationship_uses_lazy_raise(self):
        """SignalChainBlock.presets relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(SignalChainBlock, "presets")
        assert lazy_strategy is not None, "presets relationship not found"
        assert lazy_strategy == "raise", f"SignalChainBlock.presets has lazy={lazy_strategy}, expected 'raise'"

    def test_signal_chain_group_user_relationship_uses_lazy_raise(self):
        """SignalChainGroup.user relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(SignalChainGroup, "user")
        assert lazy_strategy is not None, "user relationship not found"
        assert lazy_strategy == "raise", f"SignalChainGroup.user has lazy={lazy_strategy}, expected 'raise'"

    def test_signal_chain_group_base_chain_relationship_uses_lazy_raise(self):
        """SignalChainGroup.base_chain relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(SignalChainGroup, "base_chain")
        assert lazy_strategy is not None, "base_chain relationship not found"
        assert lazy_strategy == "raise", f"SignalChainGroup.base_chain has lazy={lazy_strategy}, expected 'raise'"

    def test_shootout_chain_shootout_relationship_uses_lazy_raise(self):
        """ShootoutChain.shootout relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(ShootoutChain, "shootout")
        assert lazy_strategy is not None, "shootout relationship not found"
        assert lazy_strategy == "raise", f"ShootoutChain.shootout has lazy={lazy_strategy}, expected 'raise'"

    def test_shootout_chain_signal_chain_relationship_uses_lazy_raise(self):
        """ShootoutChain.signal_chain relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(ShootoutChain, "signal_chain")
        assert lazy_strategy is not None, "signal_chain relationship not found"
        assert lazy_strategy == "raise", f"ShootoutChain.signal_chain has lazy={lazy_strategy}, expected 'raise'"

    def test_shootout_chain_segments_relationship_uses_lazy_raise(self):
        """ShootoutChain.segments relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(ShootoutChain, "segments")
        assert lazy_strategy is not None, "segments relationship not found"
        assert lazy_strategy == "raise", f"ShootoutChain.segments has lazy={lazy_strategy}, expected 'raise'"

    def test_audio_segment_shootout_chain_relationship_uses_lazy_raise(self):
        """AudioSegment.shootout_chain relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(AudioSegment, "shootout_chain")
        assert lazy_strategy is not None, "shootout_chain relationship not found"
        assert lazy_strategy == "raise", f"AudioSegment.shootout_chain has lazy={lazy_strategy}, expected 'raise'"

    def test_block_type_blocks_relationship_uses_lazy_raise(self):
        """BlockType.blocks relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(BlockType, "blocks")
        assert lazy_strategy is not None, "blocks relationship not found"
        assert lazy_strategy == "raise", f"BlockType.blocks has lazy={lazy_strategy}, expected 'raise'"

    def test_preset_signal_chain_block_relationship_uses_lazy_raise(self):
        """Preset.signal_chain_block relationship must use lazy='raise'."""
        lazy_strategy = get_relationship_lazy_strategy(Preset, "signal_chain_block")
        assert lazy_strategy is not None, "signal_chain_block relationship not found"
        assert lazy_strategy == "raise", f"Preset.signal_chain_block has lazy={lazy_strategy}, expected 'raise'"
