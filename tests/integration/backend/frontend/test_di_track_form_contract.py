"""Tests for DI track upload form / API contract alignment (T124).

Verifies that the built frontend template uses field names and URLs
that match the actual API endpoint parameters. These are the known
bugs documented in T124:

1. hx-post URL must be "/api/v1/di-tracks" (not "/api/v1/di-tracks/upload")
2. Name input must use name="name" (not name="title")
3. Pickup input must use name="pickup" (not name="pickups")
"""

from pathlib import Path

import pytest

# Path to the built Jinja2 template (committed to git)
_TEMPLATE_PATH = Path("/app/frontend/astro/dist/pages/library/di-tracks.html")


@pytest.fixture
def template_content() -> str:
    """Read the built DI tracks library template."""
    assert _TEMPLATE_PATH.exists(), (
        f"DI tracks template not found at {_TEMPLATE_PATH}. Run 'just build-astro'."
    )
    return _TEMPLATE_PATH.read_text()


class TestUploadFormURL:
    """Upload form must post to the correct API endpoint."""

    def test_form_posts_to_correct_api_endpoint(self, template_content: str) -> None:
        """hx-post must target POST /api/v1/di-tracks (not /api/v1/di-tracks/upload).

        The API router defines: @router.post("", ...) on prefix="/api/v1/di-tracks",
        so the actual endpoint is POST /api/v1/di-tracks.
        The frontend currently has hx-post="/api/v1/di-tracks/upload" which 404s.
        """
        # The correct URL must be present
        assert 'hx-post="/api/v1/di-tracks"' in template_content, (
            "Upload form hx-post must be '/api/v1/di-tracks', not '/api/v1/di-tracks/upload'"
        )

    def test_form_does_not_use_upload_suffix(self, template_content: str) -> None:
        """Verify the /upload suffix is NOT present in the form action.

        This is the inverse check — ensures the buggy URL has been removed.
        """
        assert '/api/v1/di-tracks/upload"' not in template_content, (
            "Upload form still uses the wrong URL '/api/v1/di-tracks/upload'. "
            "Must be '/api/v1/di-tracks'"
        )


class TestUploadFormFieldNames:
    """Form field names must match API endpoint parameter names."""

    def test_name_field_uses_correct_attribute(self, template_content: str) -> None:
        """The track name input must use name="name" (not name="title").

        The API endpoint parameter is: name: Annotated[str | None, Form()]
        The frontend currently has name="title" which means the API receives
        title= (ignored) and name=None (triggers 400 "name cannot be empty").
        """
        assert 'name="name"' in template_content, (
            "Track name input must use name='name' to match API parameter. "
            "Currently uses name='title' which causes a 400 error."
        )

    def test_title_field_name_not_present(self, template_content: str) -> None:
        """Ensure the buggy name="title" field has been replaced.

        The field should be name="name", not name="title".
        The HTML attributes may span multiple lines, so we check the
        full template for name="title" as a form field (not as text content).
        """
        # Extract the upload form section (between data-testid="upload-track-form" and </form>)
        form_start = template_content.find('data-testid="upload-track-form"')
        assert form_start != -1, "Upload form not found in template"
        form_section = template_content[form_start:]
        form_end = form_section.find("</form>")
        form_section = form_section[:form_end]

        assert 'name="title"' not in form_section, (
            "Upload form still has input with name='title' — must be name='name' "
            "to match the API endpoint parameter"
        )

    def test_pickup_field_uses_correct_attribute(self, template_content: str) -> None:
        """The pickup input must use name="pickup" (not name="pickups").

        The API endpoint parameter is: pickup: Annotated[str | None, Form()]
        The frontend currently has name="pickups" (plural) which means the API
        receives pickups= (ignored) and pickup=None.
        """
        assert 'name="pickup"' in template_content, (
            "Pickup input must use name='pickup' (singular) to match API parameter. "
            "Currently uses name='pickups' (plural) which is silently ignored."
        )

    def test_pickups_plural_not_present(self, template_content: str) -> None:
        """Ensure the buggy name="pickups" (plural) has been replaced."""
        # Extract the upload form section
        form_start = template_content.find('data-testid="upload-track-form"')
        assert form_start != -1, "Upload form not found in template"
        form_section = template_content[form_start:]
        form_end = form_section.find("</form>")
        form_section = form_section[:form_end]

        assert 'name="pickups"' not in form_section, (
            "Upload form still has input with name='pickups' — must be name='pickup' (singular) "
            "to match the API endpoint parameter"
        )


class TestUploadFormCompleteness:
    """Form must include all fields accepted by the API endpoint."""

    def test_form_has_file_input(self, template_content: str) -> None:
        """Form must have file input with name="file"."""
        assert 'name="file"' in template_content, "Upload form missing file input"

    def test_form_has_name_input(self, template_content: str) -> None:
        """Form must have text input with name="name" for track name."""
        assert 'name="name"' in template_content, (
            "Upload form missing name='name' input for track title"
        )

    def test_form_has_description_field(self, template_content: str) -> None:
        """Form must have description field with name="description"."""
        assert 'name="description"' in template_content, "Upload form missing description field"

    def test_form_has_guitar_field(self, template_content: str) -> None:
        """Form must have guitar field with name="guitar"."""
        assert 'name="guitar"' in template_content, "Upload form missing guitar field"

    def test_form_has_pickup_field(self, template_content: str) -> None:
        """Form must have pickup field with name="pickup"."""
        assert 'name="pickup"' in template_content, "Upload form missing pickup field"

    def test_form_has_tuning_field(self, template_content: str) -> None:
        """Form must have tuning field with name="tuning"."""
        assert 'name="tuning"' in template_content, "Upload form missing tuning field"

    def test_form_has_multipart_encoding(self, template_content: str) -> None:
        """Form must use multipart/form-data encoding for file uploads."""
        assert 'hx-encoding="multipart/form-data"' in template_content, (
            "Upload form must use multipart/form-data encoding"
        )
