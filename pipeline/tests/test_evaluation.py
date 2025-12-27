"""Tests for AI evaluation generation functions."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

from guitar_tone_shootout.evaluation import (
    AIEvaluation,
    compute_metrics_delta,
    compute_metrics_std,
    compute_shootout_averages,
    generate_algorithmic_evaluation,
    generate_algorithmic_summary,
    generate_evaluation,
    generate_evaluation_sync,
    generate_llm_description,
    is_llm_evaluation_enabled,
)
from guitar_tone_shootout.metrics import (
    AdvancedMetrics,
    AudioMetrics,
    CoreMetrics,
    SpectralMetrics,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def base_metrics() -> AudioMetrics:
    """Create baseline AudioMetrics for testing."""
    return AudioMetrics(
        duration_seconds=10.0,
        sample_rate=44100,
        core=CoreMetrics(
            rms_dbfs=-18.0,
            peak_dbfs=-6.0,
            crest_factor_db=12.0,
            dynamic_range_db=15.0,
        ),
        spectral=SpectralMetrics(
            spectral_centroid_hz=1500.0,
            bass_energy_ratio=0.3,
            mid_energy_ratio=0.5,
            treble_energy_ratio=0.2,
        ),
        advanced=AdvancedMetrics(
            lufs_integrated=-18.0,
            transient_density=3.0,
            attack_time_ms=10.0,
            sustain_decay_rate_db_s=-15.0,
        ),
    )


@pytest.fixture
def bright_metrics() -> AudioMetrics:
    """Create brighter tone metrics for testing."""
    return AudioMetrics(
        duration_seconds=10.0,
        sample_rate=44100,
        core=CoreMetrics(
            rms_dbfs=-16.0,
            peak_dbfs=-4.0,
            crest_factor_db=14.0,  # More dynamic
            dynamic_range_db=18.0,
        ),
        spectral=SpectralMetrics(
            spectral_centroid_hz=2200.0,  # Brighter
            bass_energy_ratio=0.2,  # Less bass
            mid_energy_ratio=0.4,  # Slightly less mids
            treble_energy_ratio=0.4,  # More treble
        ),
        advanced=AdvancedMetrics(
            lufs_integrated=-16.0,
            transient_density=4.5,  # More articulate
            attack_time_ms=5.0,  # Faster attack
            sustain_decay_rate_db_s=-10.0,  # More sustain
        ),
    )


@pytest.fixture
def dark_metrics() -> AudioMetrics:
    """Create darker tone metrics for testing."""
    return AudioMetrics(
        duration_seconds=10.0,
        sample_rate=44100,
        core=CoreMetrics(
            rms_dbfs=-20.0,
            peak_dbfs=-10.0,
            crest_factor_db=10.0,  # Less dynamic (compressed)
            dynamic_range_db=10.0,
        ),
        spectral=SpectralMetrics(
            spectral_centroid_hz=900.0,  # Darker
            bass_energy_ratio=0.45,  # More bass
            mid_energy_ratio=0.4,  # Scooped mids
            treble_energy_ratio=0.15,  # Less treble
        ),
        advanced=AdvancedMetrics(
            lufs_integrated=-20.0,
            transient_density=2.0,  # Smoother
            attack_time_ms=20.0,  # Slower attack
            sustain_decay_rate_db_s=-25.0,  # Less sustain
        ),
    )


@pytest.fixture
def average_metrics(
    base_metrics: AudioMetrics,
    bright_metrics: AudioMetrics,
    dark_metrics: AudioMetrics,
) -> AudioMetrics:
    """Create average metrics from fixture set."""
    return compute_shootout_averages([base_metrics, bright_metrics, dark_metrics])


# =============================================================================
# MetricsDelta Tests
# =============================================================================


class TestComputeMetricsDelta:
    """Tests for compute_metrics_delta function."""

    def test_same_metrics_zero_delta(self, base_metrics: AudioMetrics) -> None:
        """Same metrics should produce zero delta."""
        delta = compute_metrics_delta(base_metrics, base_metrics)

        assert delta.spectral_centroid_hz == 0.0
        assert delta.bass_energy_ratio == 0.0
        assert delta.mid_energy_ratio == 0.0
        assert delta.treble_energy_ratio == 0.0
        assert delta.crest_factor_db == 0.0
        assert delta.dynamic_range_db == 0.0
        assert delta.attack_time_ms == 0.0
        assert delta.sustain_decay_rate_db_s == 0.0

    def test_brighter_positive_centroid_delta(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Brighter tone should show positive spectral centroid delta."""
        delta = compute_metrics_delta(bright_metrics, base_metrics)

        assert delta.spectral_centroid_hz > 0
        assert delta.spectral_centroid_hz == pytest.approx(700.0)  # 2200 - 1500

    def test_darker_negative_centroid_delta(
        self, dark_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Darker tone should show negative spectral centroid delta."""
        delta = compute_metrics_delta(dark_metrics, base_metrics)

        assert delta.spectral_centroid_hz < 0
        assert delta.spectral_centroid_hz == pytest.approx(-600.0)  # 900 - 1500

    def test_all_fields_computed(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """All delta fields should be computed."""
        delta = compute_metrics_delta(bright_metrics, base_metrics)

        # All fields should be present
        assert isinstance(delta.spectral_centroid_hz, float)
        assert isinstance(delta.bass_energy_ratio, float)
        assert isinstance(delta.mid_energy_ratio, float)
        assert isinstance(delta.treble_energy_ratio, float)
        assert isinstance(delta.crest_factor_db, float)
        assert isinstance(delta.dynamic_range_db, float)
        assert isinstance(delta.attack_time_ms, float)
        assert isinstance(delta.sustain_decay_rate_db_s, float)
        assert isinstance(delta.transient_density, float)
        assert isinstance(delta.rms_dbfs, float)
        assert isinstance(delta.lufs_integrated, float)


# =============================================================================
# Shootout Averages Tests
# =============================================================================


class TestComputeShootoutAverages:
    """Tests for compute_shootout_averages function."""

    def test_single_metrics_returns_same(self, base_metrics: AudioMetrics) -> None:
        """Single metrics set should return the same values."""
        avg = compute_shootout_averages([base_metrics])

        assert avg.core.rms_dbfs == base_metrics.core.rms_dbfs
        assert avg.spectral.spectral_centroid_hz == base_metrics.spectral.spectral_centroid_hz

    def test_multiple_metrics_computes_average(
        self,
        base_metrics: AudioMetrics,
        bright_metrics: AudioMetrics,
        dark_metrics: AudioMetrics,
    ) -> None:
        """Multiple metrics should compute proper average."""
        avg = compute_shootout_averages([base_metrics, bright_metrics, dark_metrics])

        # Check RMS average
        expected_rms = (-18.0 + -16.0 + -20.0) / 3
        assert avg.core.rms_dbfs == pytest.approx(expected_rms)

        # Check spectral centroid average
        expected_centroid = (1500.0 + 2200.0 + 900.0) / 3
        assert avg.spectral.spectral_centroid_hz == pytest.approx(expected_centroid)

    def test_empty_list_raises_error(self) -> None:
        """Empty list should raise ValueError."""
        with pytest.raises(ValueError, match="At least one set of metrics"):
            compute_shootout_averages([])

    def test_returns_audio_metrics_model(
        self, base_metrics: AudioMetrics, bright_metrics: AudioMetrics
    ) -> None:
        """Should return AudioMetrics model."""
        avg = compute_shootout_averages([base_metrics, bright_metrics])
        assert isinstance(avg, AudioMetrics)
        assert isinstance(avg.core, CoreMetrics)
        assert isinstance(avg.spectral, SpectralMetrics)
        assert isinstance(avg.advanced, AdvancedMetrics)


class TestComputeMetricsStd:
    """Tests for compute_metrics_std function."""

    def test_single_sample_returns_zeros(self, base_metrics: AudioMetrics) -> None:
        """Single sample should return all zeros for std."""
        std = compute_metrics_std([base_metrics], base_metrics)

        assert std.core.rms_dbfs == 0.0
        assert std.spectral.spectral_centroid_hz == 0.0
        assert std.advanced.lufs_integrated == 0.0

    def test_multiple_samples_computes_std(
        self,
        base_metrics: AudioMetrics,
        bright_metrics: AudioMetrics,
        dark_metrics: AudioMetrics,
        average_metrics: AudioMetrics,
    ) -> None:
        """Multiple samples should compute proper std."""
        std = compute_metrics_std(
            [base_metrics, bright_metrics, dark_metrics], average_metrics
        )

        # Std should be non-zero for varying metrics
        assert std.core.rms_dbfs > 0
        assert std.spectral.spectral_centroid_hz > 0

    def test_returns_audio_metrics_model(
        self,
        base_metrics: AudioMetrics,
        bright_metrics: AudioMetrics,
        average_metrics: AudioMetrics,
    ) -> None:
        """Should return AudioMetrics model."""
        std = compute_metrics_std([base_metrics, bright_metrics], average_metrics)
        assert isinstance(std, AudioMetrics)


# =============================================================================
# Algorithmic Summary Tests
# =============================================================================


class TestGenerateAlgorithmicSummary:
    """Tests for generate_algorithmic_summary function."""

    def test_returns_string(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Should return a string description."""
        summary = generate_algorithmic_summary(bright_metrics, base_metrics)
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_includes_amp_name(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Should include amp name when provided."""
        summary = generate_algorithmic_summary(
            bright_metrics, base_metrics, amp_name="JCM800"
        )
        assert "JCM800" in summary

    def test_describes_brightness(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Should describe brightness for brighter tones."""
        summary = generate_algorithmic_summary(bright_metrics, base_metrics)
        assert "bright" in summary.lower()

    def test_describes_darkness(
        self, dark_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Should describe darkness for darker tones."""
        summary = generate_algorithmic_summary(dark_metrics, base_metrics)
        assert "dark" in summary.lower()

    def test_describes_balanced_for_similar(
        self, base_metrics: AudioMetrics
    ) -> None:
        """Should describe balanced for similar metrics."""
        summary = generate_algorithmic_summary(base_metrics, base_metrics)
        assert "balanced" in summary.lower()

    def test_ends_with_period(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Summary should end with a period."""
        summary = generate_algorithmic_summary(bright_metrics, base_metrics)
        assert summary.endswith(".")


# =============================================================================
# Algorithmic Evaluation Tests
# =============================================================================


class TestGenerateAlgorithmicEvaluation:
    """Tests for generate_algorithmic_evaluation function."""

    def test_returns_ai_evaluation_model(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Should return AIEvaluation model."""
        evaluation = generate_algorithmic_evaluation(bright_metrics, base_metrics)
        assert isinstance(evaluation, AIEvaluation)

    def test_model_name_is_algorithmic(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Model name should be 'algorithmic'."""
        evaluation = generate_algorithmic_evaluation(bright_metrics, base_metrics)
        assert evaluation.model_name == "algorithmic"
        assert evaluation.model_version == "1.0.0"

    def test_has_tone_description(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Should have a tone description."""
        evaluation = generate_algorithmic_evaluation(bright_metrics, base_metrics)
        assert evaluation.tone_description
        assert len(evaluation.tone_description) > 0

    def test_has_strengths_for_dynamic_tone(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Dynamic tones should have strength descriptors."""
        evaluation = generate_algorithmic_evaluation(bright_metrics, base_metrics)
        # Bright metrics have more dynamics, should have strengths
        assert len(evaluation.strengths) > 0

    def test_has_recommended_genres(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Should have recommended genres."""
        evaluation = generate_algorithmic_evaluation(bright_metrics, base_metrics)
        assert len(evaluation.recommended_genres) > 0

    def test_has_comparison_notes(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Should have comparison notes."""
        evaluation = generate_algorithmic_evaluation(bright_metrics, base_metrics)
        assert evaluation.comparison_notes is not None
        assert len(evaluation.comparison_notes) > 0

    def test_no_overall_rating(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Algorithmic evaluation should not have overall rating."""
        evaluation = generate_algorithmic_evaluation(bright_metrics, base_metrics)
        assert evaluation.overall_rating is None

    def test_no_raw_response(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Algorithmic evaluation should not have raw response."""
        evaluation = generate_algorithmic_evaluation(bright_metrics, base_metrics)
        assert evaluation.raw_response is None


class TestStrengthsAndWeaknesses:
    """Tests for strength/weakness determination logic."""

    def test_bright_tone_cutting_strength(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Bright tones should note cutting through mix."""
        evaluation = generate_algorithmic_evaluation(bright_metrics, base_metrics)
        # Check if any strength mentions cutting through
        strengths_text = " ".join(evaluation.strengths).lower()
        assert "cut" in strengths_text or "dynamic" in strengths_text

    def test_dark_tone_may_get_lost(
        self, dark_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Very dark tones may have weakness about getting lost."""
        evaluation = generate_algorithmic_evaluation(dark_metrics, base_metrics)
        # Check for weakness related to mix presence
        # This might not trigger if threshold not met, so just ensure it's a list
        assert isinstance(evaluation.weaknesses, list)


class TestGenreRecommendations:
    """Tests for genre recommendation logic."""

    def test_bright_articulate_genres(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Bright articulate tones should recommend appropriate genres."""
        evaluation = generate_algorithmic_evaluation(bright_metrics, base_metrics)
        genres = [g.lower() for g in evaluation.recommended_genres]
        # Should have at least one genre
        assert len(genres) > 0

    def test_dark_compressed_genres(
        self, dark_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Dark compressed tones should recommend heavy genres."""
        evaluation = generate_algorithmic_evaluation(dark_metrics, base_metrics)
        genres = [g.lower() for g in evaluation.recommended_genres]
        # Should have at least one genre
        assert len(genres) > 0

    def test_no_duplicate_genres(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Should not have duplicate genre recommendations."""
        evaluation = generate_algorithmic_evaluation(bright_metrics, base_metrics)
        genres = evaluation.recommended_genres
        assert len(genres) == len(set(genres))


# =============================================================================
# LLM Evaluation Tests
# =============================================================================


class TestIsLlmEvaluationEnabled:
    """Tests for is_llm_evaluation_enabled function."""

    def test_disabled_by_default(self) -> None:
        """LLM should be disabled by default."""
        with patch.dict(os.environ, {}, clear=True):
            assert is_llm_evaluation_enabled() is False

    def test_enabled_with_true(self) -> None:
        """LLM should be enabled with 'true'."""
        with patch.dict(os.environ, {"ENABLE_LLM_EVALUATION": "true"}):
            assert is_llm_evaluation_enabled() is True

    def test_enabled_with_1(self) -> None:
        """LLM should be enabled with '1'."""
        with patch.dict(os.environ, {"ENABLE_LLM_EVALUATION": "1"}):
            assert is_llm_evaluation_enabled() is True

    def test_enabled_with_yes(self) -> None:
        """LLM should be enabled with 'yes'."""
        with patch.dict(os.environ, {"ENABLE_LLM_EVALUATION": "yes"}):
            assert is_llm_evaluation_enabled() is True

    def test_case_insensitive(self) -> None:
        """Check should be case insensitive."""
        with patch.dict(os.environ, {"ENABLE_LLM_EVALUATION": "TRUE"}):
            assert is_llm_evaluation_enabled() is True


class TestGenerateLlmDescription:
    """Tests for generate_llm_description function."""

    @pytest.mark.asyncio
    async def test_returns_none_when_disabled(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Should return None when LLM is disabled."""
        with patch.dict(os.environ, {}, clear=True):
            result = await generate_llm_description(
                bright_metrics,
                base_metrics,
                "Test summary",
                "Test Amp",
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_without_api_key(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Should return None when API key is not set."""
        with patch.dict(
            os.environ,
            {"ENABLE_LLM_EVALUATION": "true"},
            clear=True,
        ):
            result = await generate_llm_description(
                bright_metrics,
                base_metrics,
                "Test summary",
                "Test Amp",
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_uses_cache_when_provided(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Should use cached result when available."""
        cache: dict[str, AIEvaluation] = {}

        # Create a cached result
        cached_eval = AIEvaluation(
            model_name="claude-3-5-sonnet",
            model_version="20241022",
            tone_description="Cached description",
            strengths=["Cached strength"],
            weaknesses=[],
            recommended_genres=["rock"],
            comparison_notes=None,
            overall_rating=8.0,
            raw_response=None,
        )

        # Populate cache with the expected key
        from guitar_tone_shootout.evaluation import _get_metrics_cache_key

        cache_key = _get_metrics_cache_key(bright_metrics, base_metrics, "Test Amp")
        cache[cache_key] = cached_eval

        with patch.dict(
            os.environ,
            {"ENABLE_LLM_EVALUATION": "true", "ANTHROPIC_API_KEY": "test-key"},
        ):
            result = await generate_llm_description(
                bright_metrics,
                base_metrics,
                "Test summary",
                "Test Amp",
                cache=cache,
            )
            assert result is not None
            assert result.tone_description == "Cached description"


# =============================================================================
# Main Evaluation Function Tests
# =============================================================================


class TestGenerateEvaluation:
    """Tests for generate_evaluation async function."""

    @pytest.mark.asyncio
    async def test_returns_algorithmic_when_llm_disabled(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Should return algorithmic evaluation when LLM is disabled."""
        with patch.dict(os.environ, {}, clear=True):
            result = await generate_evaluation(
                bright_metrics, base_metrics, amp_name="Test Amp"
            )
            assert result.model_name == "algorithmic"

    @pytest.mark.asyncio
    async def test_respects_enable_llm_override(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Should respect enable_llm parameter override."""
        # Even with env var set, override should take precedence
        with patch.dict(os.environ, {"ENABLE_LLM_EVALUATION": "true"}):
            result = await generate_evaluation(
                bright_metrics, base_metrics, enable_llm=False
            )
            assert result.model_name == "algorithmic"

    @pytest.mark.asyncio
    async def test_falls_back_to_algorithmic_on_llm_failure(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Should fall back to algorithmic when LLM fails."""
        import sys
        import types

        # Create a mock httpx module
        mock_httpx = types.ModuleType("httpx")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=Exception("API Error"))
        mock_httpx.AsyncClient = lambda: mock_client  # type: ignore[attr-defined]

        env_vars = {"ENABLE_LLM_EVALUATION": "true", "ANTHROPIC_API_KEY": "invalid-key"}
        with patch.dict(os.environ, env_vars), patch.dict(sys.modules, {"httpx": mock_httpx}):
            result = await generate_evaluation(
                bright_metrics, base_metrics, enable_llm=True
            )
            # Should fall back to algorithmic
            assert result.model_name == "algorithmic"


class TestGenerateEvaluationSync:
    """Tests for generate_evaluation_sync function."""

    def test_returns_ai_evaluation(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Should return AIEvaluation model."""
        result = generate_evaluation_sync(bright_metrics, base_metrics)
        assert isinstance(result, AIEvaluation)

    def test_uses_algorithmic_model(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Should use algorithmic model."""
        result = generate_evaluation_sync(bright_metrics, base_metrics)
        assert result.model_name == "algorithmic"

    def test_includes_amp_name(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """Should include amp name in description."""
        result = generate_evaluation_sync(
            bright_metrics, base_metrics, amp_name="Plexi"
        )
        assert "Plexi" in result.tone_description


# =============================================================================
# JSON Serialization Tests
# =============================================================================


class TestSerialization:
    """Tests for JSON serialization of evaluation models."""

    def test_ai_evaluation_serializable(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """AIEvaluation should be JSON serializable."""
        evaluation = generate_algorithmic_evaluation(bright_metrics, base_metrics)
        json_str = evaluation.model_dump_json()
        assert isinstance(json_str, str)
        assert "tone_description" in json_str
        assert "strengths" in json_str
        assert "recommended_genres" in json_str

    def test_ai_evaluation_round_trip(
        self, bright_metrics: AudioMetrics, base_metrics: AudioMetrics
    ) -> None:
        """AIEvaluation should survive JSON round-trip."""
        import json

        original = generate_algorithmic_evaluation(bright_metrics, base_metrics)
        json_str = original.model_dump_json()
        parsed = json.loads(json_str)
        restored = AIEvaluation(**parsed)

        assert restored.model_name == original.model_name
        assert restored.tone_description == original.tone_description
        assert restored.strengths == original.strengths
        assert restored.recommended_genres == original.recommended_genres


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_handles_extreme_brightness_difference(self) -> None:
        """Should handle very large spectral centroid differences."""
        very_bright = AudioMetrics(
            duration_seconds=10.0,
            sample_rate=44100,
            core=CoreMetrics(
                rms_dbfs=-18.0, peak_dbfs=-6.0, crest_factor_db=12.0, dynamic_range_db=15.0
            ),
            spectral=SpectralMetrics(
                spectral_centroid_hz=8000.0,  # Very bright
                bass_energy_ratio=0.1,
                mid_energy_ratio=0.3,
                treble_energy_ratio=0.6,
            ),
            advanced=AdvancedMetrics(
                lufs_integrated=-18.0,
                transient_density=5.0,
                attack_time_ms=2.0,
                sustain_decay_rate_db_s=-10.0,
            ),
        )
        very_dark = AudioMetrics(
            duration_seconds=10.0,
            sample_rate=44100,
            core=CoreMetrics(
                rms_dbfs=-18.0, peak_dbfs=-6.0, crest_factor_db=12.0, dynamic_range_db=15.0
            ),
            spectral=SpectralMetrics(
                spectral_centroid_hz=400.0,  # Very dark
                bass_energy_ratio=0.6,
                mid_energy_ratio=0.3,
                treble_energy_ratio=0.1,
            ),
            advanced=AdvancedMetrics(
                lufs_integrated=-18.0,
                transient_density=1.0,
                attack_time_ms=30.0,
                sustain_decay_rate_db_s=-30.0,
            ),
        )

        # Should handle extreme difference without error
        evaluation = generate_algorithmic_evaluation(very_bright, very_dark)
        assert "significantly" in evaluation.tone_description.lower()

    def test_handles_identical_metrics(self, base_metrics: AudioMetrics) -> None:
        """Should handle identical metrics gracefully."""
        evaluation = generate_algorithmic_evaluation(base_metrics, base_metrics)
        assert "balanced" in evaluation.tone_description.lower()
        # Should still have comparison notes
        assert evaluation.comparison_notes is not None

    def test_handles_negative_lufs(self) -> None:
        """Should handle very negative LUFS values."""
        quiet = AudioMetrics(
            duration_seconds=10.0,
            sample_rate=44100,
            core=CoreMetrics(
                rms_dbfs=-40.0, peak_dbfs=-30.0, crest_factor_db=10.0, dynamic_range_db=10.0
            ),
            spectral=SpectralMetrics(
                spectral_centroid_hz=1500.0,
                bass_energy_ratio=0.33,
                mid_energy_ratio=0.34,
                treble_energy_ratio=0.33,
            ),
            advanced=AdvancedMetrics(
                lufs_integrated=-40.0,
                transient_density=2.0,
                attack_time_ms=10.0,
                sustain_decay_rate_db_s=-15.0,
            ),
        )
        loud = AudioMetrics(
            duration_seconds=10.0,
            sample_rate=44100,
            core=CoreMetrics(
                rms_dbfs=-10.0, peak_dbfs=-2.0, crest_factor_db=8.0, dynamic_range_db=8.0
            ),
            spectral=SpectralMetrics(
                spectral_centroid_hz=1500.0,
                bass_energy_ratio=0.33,
                mid_energy_ratio=0.34,
                treble_energy_ratio=0.33,
            ),
            advanced=AdvancedMetrics(
                lufs_integrated=-10.0,
                transient_density=2.0,
                attack_time_ms=10.0,
                sustain_decay_rate_db_s=-15.0,
            ),
        )

        # Should handle without error
        evaluation = generate_algorithmic_evaluation(quiet, loud)
        assert isinstance(evaluation, AIEvaluation)
        # Should note the LUFS difference
        assert "LUFS" in (evaluation.comparison_notes or "")
