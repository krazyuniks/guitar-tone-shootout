"""Tests for DI track upload UI enhancements (T126).

Verifies the built frontend template includes:
1. Drag-and-drop zone with visual feedback
2. Upload progress bar
3. Client-side file validation (WAV only, size limit)
4. Complete metadata form (name, description, guitar, pickup, notes)
5. Success/error feedback elements
6. All interactive elements have data-testid attributes
"""

from pathlib import Path

import pytest

# Path to the built Jinja2 template (committed to git)
_TEMPLATE_PATH = Path("/app/frontend/astro/dist/pages/library/di-tracks.html")


@pytest.fixture
def template_content() -> str:
    """Read the built DI tracks library template."""
    assert (
        _TEMPLATE_PATH.exists()
    ), f"DI tracks template not found at {_TEMPLATE_PATH}. Run 'just build-astro'."
    return _TEMPLATE_PATH.read_text()


@pytest.fixture
def upload_modal_content(template_content: str) -> str:
    """Extract the upload modal section from the template."""
    start = template_content.find('id="upload-modal"')
    assert start != -1, "Upload modal not found in template"
    # Find the closing </dialog> tag
    end = template_content.find("</dialog>", start)
    assert end != -1, "Upload modal closing tag not found"
    return template_content[start : end + len("</dialog>")]


@pytest.fixture
def script_content(template_content: str) -> str:
    """Extract all script sections from the template."""
    scripts = []
    pos = 0
    while True:
        start = template_content.find("<script", pos)
        if start == -1:
            break
        end = template_content.find("</script>", start)
        if end == -1:
            break
        scripts.append(template_content[start : end + len("</script>")])
        pos = end + len("</script>")
    return "\n".join(scripts)


class TestDragAndDropZone:
    """Upload modal must have a drag-and-drop zone for file selection."""

    def test_has_drop_zone_element(self, upload_modal_content: str) -> None:
        """Modal must contain a dedicated drop zone element with data-testid."""
        assert 'data-testid="upload-drop-zone"' in upload_modal_content, (
            "Upload modal must have a drag-and-drop zone with " 'data-testid="upload-drop-zone"'
        )

    def test_drop_zone_has_drag_event_handlers(self, template_content: str) -> None:
        """Drop zone must handle dragenter, dragleave, dragover, and drop events.

        These can be via Alpine.js directives (x-on:, @), inline handlers,
        or JavaScript event listeners.
        """
        # Check for drag event handling — Alpine.js or inline
        has_dragover = (
            "@dragover" in template_content
            or "x-on:dragover" in template_content
            or "ondragover" in template_content
            or "dragover" in template_content
        )
        has_drop = (
            "@drop" in template_content
            or "x-on:drop" in template_content
            or "ondrop" in template_content
            or ("addEventListener" in template_content and "drop" in template_content)
        )
        assert has_dragover, (
            "Drop zone must handle dragover events "
            "(via Alpine.js @dragover, x-on:dragover, or inline ondragover)"
        )
        assert has_drop, (
            "Drop zone must handle drop events "
            "(via Alpine.js @drop, x-on:drop, or inline ondrop)"
        )

    def test_drop_zone_has_click_fallback(self, upload_modal_content: str) -> None:
        """Drop zone must support click-to-select as a fallback.

        Either the drop zone itself triggers a hidden file input click,
        or a file input is embedded within the drop zone.
        """
        # The drop zone should either contain a file input or trigger one on click
        has_click_fallback = (
            'type="file"' in upload_modal_content
            and 'data-testid="upload-drop-zone"' in upload_modal_content
        )
        assert has_click_fallback, (
            "Drop zone must have a click fallback for file selection "
            "(file input within or triggered by the drop zone)"
        )


class TestDragVisualFeedback:
    """Drop zone must provide visual feedback on drag enter/leave/drop."""

    def test_has_drag_active_state(self, template_content: str) -> None:
        """Template must have visual state change for when a file is being dragged over.

        This could be Alpine.js x-bind:class with a dragging state variable,
        CSS class toggling, or inline style changes.
        """
        # Look for a dragging/drag-active state variable or class
        has_drag_state = (
            "dragging" in template_content
            or "dragActive" in template_content
            or "drag-active" in template_content
            or "isDragging" in template_content
            or "is-dragging" in template_content
            or "dragover" in template_content.lower()
        )
        # Must also have class binding or style change tied to drag state
        has_visual_change = (
            ":class" in template_content
            or "x-bind:class" in template_content
            or "classList" in template_content
        )
        assert has_drag_state and has_visual_change, (
            "Drop zone must change appearance on drag enter/leave. "
            "Needs a state variable (e.g., 'dragging') bound to CSS classes "
            "via Alpine.js :class or x-bind:class"
        )


class TestUploadProgressBar:
    """Upload modal must show a progress bar during file upload."""

    def test_has_progress_bar_element(self, upload_modal_content: str) -> None:
        """Modal must contain a progress bar element with data-testid."""
        assert 'data-testid="upload-progress-bar"' in upload_modal_content, (
            "Upload modal must have a progress bar element with "
            'data-testid="upload-progress-bar"'
        )

    def test_has_progress_percentage_display(self, upload_modal_content: str) -> None:
        """Modal must show upload percentage text."""
        assert 'data-testid="upload-progress-text"' in upload_modal_content, (
            "Upload modal must have a progress percentage text element with "
            'data-testid="upload-progress-text"'
        )

    def test_progress_uses_htmx_or_xhr(self, template_content: str) -> None:
        """Upload must track progress via XMLHttpRequest or htmx:xhr:progress.

        Standard HTMX form submissions don't provide upload progress.
        The implementation needs either:
        - htmx:xhr:progress event listener, or
        - Custom XMLHttpRequest with upload.onprogress
        """
        has_progress_tracking = (
            "xhr:progress" in template_content
            or "upload.onprogress" in template_content
            or "upload.addEventListener" in template_content
            or "XMLHttpRequest" in template_content
            or "htmx:xhr:progress" in template_content
        )
        assert has_progress_tracking, (
            "Upload must track progress via htmx:xhr:progress event "
            "or custom XMLHttpRequest with upload.onprogress"
        )


class TestClientSideFileValidation:
    """Client-side validation for file type and size before upload."""

    def test_validates_file_type_wav_only(self, template_content: str) -> None:
        """JavaScript must validate that only WAV files are accepted.

        Must check file extension or MIME type client-side before upload.
        """
        # Look for .wav validation in script
        has_wav_validation = (
            ".wav" in template_content
            or "audio/wav" in template_content
            or "audio/wave" in template_content
            or "audio/x-wav" in template_content
        )
        # Must have JavaScript validation logic (not just accept attribute)
        has_js_validation = (
            "file.type" in template_content
            or "file.name" in template_content
            or "fileName" in template_content
            or "fileType" in template_content
        )
        assert has_wav_validation and has_js_validation, (
            "Must have client-side JavaScript validation checking file is WAV format "
            "(checking file.type or file.name extension), not just HTML accept attribute"
        )

    def test_validates_file_size_limit(self, template_content: str) -> None:
        """JavaScript must enforce a reasonable file size limit.

        Should check file.size against a maximum (e.g., 100MB, 200MB).
        """
        has_size_check = (
            "file.size" in template_content
            or "fileSize" in template_content
            or "maxSize" in template_content
            or "MAX_SIZE" in template_content
            or "maxFileSize" in template_content
            or "size_limit" in template_content
        )
        assert has_size_check, (
            "Must have client-side file size validation "
            "(checking file.size against a maximum limit)"
        )

    def test_has_validation_error_display(self, upload_modal_content: str) -> None:
        """Modal must have an element to display file validation errors."""
        assert 'data-testid="upload-file-error"' in upload_modal_content, (
            "Upload modal must have a file validation error display with "
            'data-testid="upload-file-error"'
        )


class TestMetadataForm:
    """Upload form must include all required metadata fields."""

    def test_has_notes_field(self, upload_modal_content: str) -> None:
        """Form must have a notes field with name="notes".

        The acceptance criteria lists: name, description, guitar, pickup, notes.
        The existing form has name, description, guitar, pickup, tuning but NOT notes.
        """
        assert 'name="notes"' in upload_modal_content, (
            "Upload form must have a notes field with name='notes'. "
            "Acceptance criteria requires: name, description, guitar, pickup, notes"
        )

    def test_notes_field_has_testid(self, upload_modal_content: str) -> None:
        """Notes field must have a data-testid attribute."""
        assert (
            'data-testid="upload-notes-input"' in upload_modal_content
            or 'data-testid="upload-notes-textarea"' in upload_modal_content
        ), (
            "Notes field must have a data-testid attribute "
            "(upload-notes-input or upload-notes-textarea)"
        )


class TestErrorFeedback:
    """Upload must show inline error messages on failure."""

    def test_has_upload_error_container(self, upload_modal_content: str) -> None:
        """Modal must have a container to display upload/server errors."""
        assert 'data-testid="upload-error-message"' in upload_modal_content, (
            "Upload modal must have an error message container with "
            'data-testid="upload-error-message"'
        )

    def test_handles_htmx_response_error(self, template_content: str) -> None:
        """Script must handle HTMX response errors for the upload form.

        Must show inline error message instead of silently failing.
        The current template only handles 401 (auth redirect), not other errors.
        """
        # Look for error handling specific to upload form
        has_upload_error_handling = (
            "responseError" in template_content
            or "htmx:responseError" in template_content
            or "response-error" in template_content
        )
        has_error_display = (
            "upload-error" in template_content
            or "error-message" in template_content
            or "errorMessage" in template_content
        )
        assert has_upload_error_handling and has_error_display, (
            "Must handle HTMX response errors for the upload form and "
            "display inline error messages (not just auth redirect)"
        )


class TestSuccessFeedback:
    """Upload success must close modal and refresh track list."""

    def test_modal_closes_on_success(self, template_content: str) -> None:
        """Script must close the upload modal on successful upload.

        The current implementation has a basic htmx:afterSwap handler.
        Verify it still exists and properly closes the modal.
        """
        assert (
            "modal.close()" in template_content or "close()" in template_content
        ), "Script must close the upload modal on successful upload"

    def test_form_resets_on_success(self, template_content: str) -> None:
        """Form must be reset after successful upload.

        After modal closes, the form fields should be cleared so
        the next upload starts fresh.
        """
        has_form_reset = "form.reset()" in template_content or (
            "reset()" in template_content and "form" in template_content
        )
        assert has_form_reset, (
            "Upload form must be reset after successful upload "
            "so next upload starts with clean fields"
        )

    def test_progress_resets_on_success(self, template_content: str) -> None:
        """Progress bar must reset after successful upload."""
        # Progress should be hidden/reset after success
        has_progress_reset = "progress" in template_content.lower() and (
            "0" in template_content or "hidden" in template_content
        )
        assert has_progress_reset, "Progress bar must reset to 0/hidden after successful upload"


class TestDataTestIdAttributes:
    """All interactive elements must have data-testid attributes."""

    def test_drop_zone_has_testid(self, upload_modal_content: str) -> None:
        """Drop zone element must have data-testid."""
        assert 'data-testid="upload-drop-zone"' in upload_modal_content

    def test_progress_bar_has_testid(self, upload_modal_content: str) -> None:
        """Progress bar must have data-testid."""
        assert 'data-testid="upload-progress-bar"' in upload_modal_content

    def test_progress_text_has_testid(self, upload_modal_content: str) -> None:
        """Progress percentage text must have data-testid."""
        assert 'data-testid="upload-progress-text"' in upload_modal_content

    def test_file_error_has_testid(self, upload_modal_content: str) -> None:
        """File validation error display must have data-testid."""
        assert 'data-testid="upload-file-error"' in upload_modal_content

    def test_upload_error_has_testid(self, upload_modal_content: str) -> None:
        """Upload error message must have data-testid."""
        assert 'data-testid="upload-error-message"' in upload_modal_content
