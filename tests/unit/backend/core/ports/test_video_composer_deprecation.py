"""Unit tests for VideoComposer protocol deprecation.

Tests that the old VideoComposer protocol is either removed or deprecated
in favour of the new generic VideoRenderer port.
"""

import pytest


class TestVideoComposerDeprecation:
    """Test that VideoComposer is removed or marked deprecated."""

    def test_video_composer_is_removed_or_deprecated(self) -> None:
        """VideoComposer should be removed or have deprecation warning."""
        try:
            # If it still exists, check for deprecation markers
            import warnings

            from gts.ports.video_composer import VideoComposer

            # Check if the module has a deprecation notice in docstring
            if VideoComposer.__doc__:
                doc_lower = VideoComposer.__doc__.lower()
                assert "deprecated" in doc_lower or "use videorenderer" in doc_lower, (
                    "VideoComposer should be marked as deprecated"
                )

            # Check if importing triggers a deprecation warning
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                from gts.ports.video_composer import VideoComposer

                # If no deprecation warning, the test should document this
                if len(w) == 0:
                    pytest.fail(
                        "VideoComposer exists but has no deprecation warning. "
                        "Consider adding DeprecationWarning or removing the module."
                    )

        except ModuleNotFoundError:
            # VideoComposer has been removed - this is the expected outcome
            pass

    def test_video_renderer_replaces_video_composer(self) -> None:
        """VideoRenderer should exist as the replacement for VideoComposer."""
        # This test ensures the new port exists
        from gts.ports.video_renderer import VideoRenderer

        assert VideoRenderer is not None
        assert hasattr(VideoRenderer, "submit")
        assert hasattr(VideoRenderer, "poll")
