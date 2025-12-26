"""Tests for configuration loading and parsing."""

from pathlib import Path

import pytest

from guitar_tone_shootout.config import (
    ChainEffect,
    Comparison,
    ComparisonMeta,
    DITrack,
    SignalChain,
    _parse_chain,
    load_comparison,
)


class TestComparisonMeta:
    """Tests for ComparisonMeta dataclass."""

    def test_create_meta(self) -> None:
        meta = ComparisonMeta(
            name="Test Comparison",
            author="tester",
        )
        assert meta.name == "Test Comparison"
        assert meta.author == "tester"
        assert meta.description == ""

    def test_create_meta_with_description(self) -> None:
        meta = ComparisonMeta(
            name="Test",
            author="tester",
            description="A test comparison",
        )
        assert meta.description == "A test comparison"


class TestDITrack:
    """Tests for DITrack dataclass."""

    def test_create_di_track(self) -> None:
        track = DITrack(
            file=Path("inputs/di_tracks/test.wav"),
            guitar="Fender Stratocaster",
            pickup="bridge single coil",
        )
        assert track.file == Path("inputs/di_tracks/test.wav")
        assert track.guitar == "Fender Stratocaster"
        assert track.pickup == "bridge single coil"
        assert track.notes == ""

    def test_create_di_track_with_notes(self) -> None:
        track = DITrack(
            file=Path("test.wav"),
            guitar="Gibson Les Paul",
            pickup="neck humbucker",
            notes="recorded hot",
        )
        assert track.notes == "recorded hot"


class TestChainEffect:
    """Tests for ChainEffect dataclass."""

    def test_create_chain_effect(self) -> None:
        effect = ChainEffect(effect_type="nam", value="plexi.nam")
        assert effect.effect_type == "nam"
        assert effect.value == "plexi.nam"


class TestSignalChain:
    """Tests for SignalChain dataclass."""

    def test_create_signal_chain(self) -> None:
        chain = SignalChain(
            name="Plexi Crunch",
            description="Classic British tone",
            chain=[
                ChainEffect("nam", "plexi.nam"),
                ChainEffect("ir", "greenback.wav"),
            ],
        )
        assert chain.name == "Plexi Crunch"
        assert chain.description == "Classic British tone"
        assert len(chain.chain) == 2


class TestParseChain:
    """Tests for _parse_chain function."""

    def test_parse_simple_chain(self) -> None:
        effects = _parse_chain("nam:plexi.nam, ir:greenback.wav")
        assert len(effects) == 2
        assert effects[0].effect_type == "nam"
        assert effects[0].value == "plexi.nam"
        assert effects[1].effect_type == "ir"
        assert effects[1].value == "greenback.wav"

    def test_parse_chain_with_path(self) -> None:
        effects = _parse_chain("nam:tone3000/user/pack/model.nam")
        assert effects[0].value == "tone3000/user/pack/model.nam"

    def test_parse_chain_multiple_effects(self) -> None:
        effects = _parse_chain("eq:highpass_80hz, nam:plexi.nam, ir:cab.wav, reverb:hall")
        assert len(effects) == 4
        assert effects[0].effect_type == "eq"
        assert effects[1].effect_type == "nam"
        assert effects[2].effect_type == "ir"
        assert effects[3].effect_type == "reverb"

    def test_parse_chain_invalid_format(self) -> None:
        with pytest.raises(ValueError, match="Invalid chain effect format"):
            _parse_chain("invalid_no_colon")

    def test_parse_chain_unknown_type(self) -> None:
        with pytest.raises(ValueError, match="Unknown effect type"):
            _parse_chain("unknown:value")


class TestComparison:
    """Tests for Comparison dataclass."""

    def test_segment_count(self) -> None:
        comparison = Comparison(
            meta=ComparisonMeta(name="Test", author="test"),
            di_tracks=[
                DITrack(Path("di1.wav"), "Guitar1", "pickup1"),
                DITrack(Path("di2.wav"), "Guitar2", "pickup2"),
            ],
            signal_chains=[
                SignalChain("Chain1", "Desc1", [ChainEffect("nam", "amp.nam")]),
                SignalChain("Chain2", "Desc2", [ChainEffect("nam", "amp2.nam")]),
                SignalChain("Chain3", "Desc3", [ChainEffect("nam", "amp3.nam")]),
            ],
        )
        # 2 DI tracks * 3 signal chains = 6 segments
        assert comparison.segment_count == 6

    def test_get_segments_order(self) -> None:
        """Test that segments follow signal_chains outer, di_tracks inner."""
        di1 = DITrack(Path("di1.wav"), "Guitar1", "pickup1")
        di2 = DITrack(Path("di2.wav"), "Guitar2", "pickup2")
        chain1 = SignalChain("Chain1", "Desc1", [ChainEffect("nam", "amp1.nam")])
        chain2 = SignalChain("Chain2", "Desc2", [ChainEffect("nam", "amp2.nam")])

        comparison = Comparison(
            meta=ComparisonMeta(name="Test", author="test"),
            di_tracks=[di1, di2],
            signal_chains=[chain1, chain2],
        )

        segments = comparison.get_segments()

        # Order: chain1+di1, chain1+di2, chain2+di1, chain2+di2
        assert segments[0] == (di1, chain1)
        assert segments[1] == (di2, chain1)
        assert segments[2] == (di1, chain2)
        assert segments[3] == (di2, chain2)


class TestLoadComparison:
    """Tests for load_comparison function."""

    def test_missing_section_raises(self, tmp_path: Path) -> None:
        ini_content = """
[meta]
name = Test
author = tester

[di_tracks]
1.file = test.wav
1.guitar = Test Guitar
1.pickup = bridge
"""
        ini_file = tmp_path / "test.ini"
        ini_file.write_text(ini_content)

        with pytest.raises(ValueError, match="Missing required section"):
            load_comparison(ini_file)

    def test_load_valid_comparison(self, tmp_path: Path) -> None:
        ini_content = """
[meta]
name = Test Comparison
author = tester
description = A test

[di_tracks]
1.file = test.wav
1.guitar = Fender Strat
1.pickup = bridge

[signal_chains]
1.name = Test Chain
1.description = A test chain
1.chain = nam:test.nam, ir:test.wav
"""
        ini_file = tmp_path / "test.ini"
        ini_file.write_text(ini_content)

        comparison = load_comparison(ini_file)

        assert comparison.meta.name == "Test Comparison"
        assert comparison.meta.author == "tester"
        assert len(comparison.di_tracks) == 1
        assert len(comparison.signal_chains) == 1
        assert comparison.di_tracks[0].guitar == "Fender Strat"
        assert comparison.signal_chains[0].name == "Test Chain"
        assert len(comparison.signal_chains[0].chain) == 2

    def test_missing_di_track_file_raises(self, tmp_path: Path) -> None:
        ini_content = """
[meta]
name = Test

[di_tracks]
1.guitar = Strat

[signal_chains]
1.name = Chain
1.chain = nam:test.nam
"""
        ini_file = tmp_path / "test.ini"
        ini_file.write_text(ini_content)

        with pytest.raises(ValueError, match="missing required 'file' field"):
            load_comparison(ini_file)

    def test_missing_chain_name_raises(self, tmp_path: Path) -> None:
        ini_content = """
[meta]
name = Test

[di_tracks]
1.file = test.wav
1.guitar = Strat
1.pickup = bridge

[signal_chains]
1.chain = nam:test.nam
"""
        ini_file = tmp_path / "test.ini"
        ini_file.write_text(ini_content)

        with pytest.raises(ValueError, match="missing required 'name' field"):
            load_comparison(ini_file)
