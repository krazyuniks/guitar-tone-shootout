"""Unit tests for ModelDownloader integration into sync_service.

Verifies that sync_service.py imports and calls ModelDownloader after model
staging, and wraps download calls with error handling so failures don't crash
the sync loop.

Uses inspect.getsource() for static source analysis — this is a wiring task,
not a behaviour test. The ModelDownloader itself is tested separately.
"""

import ast
import inspect
import textwrap

from source_t3k.services.sync_service import T3KSyncService


class TestSyncServiceImportsModelDownloader:
    """Verify sync_service.py imports ModelDownloader."""

    def test_sync_service_module_imports_model_downloader(self) -> None:
        """sync_service.py must import ModelDownloader from model_downloader module."""
        module_source = inspect.getmodule(T3KSyncService)
        assert module_source is not None, "T3KSyncService must belong to an importable module"

        full_source = inspect.getsource(module_source)
        assert "ModelDownloader" in full_source, "sync_service.py must import ModelDownloader"

    def test_sync_service_module_imports_from_correct_module(self) -> None:
        """sync_service.py must import ModelDownloader from source_t3k.services.model_downloader."""
        module = inspect.getmodule(T3KSyncService)
        assert module is not None, "T3KSyncService must belong to an importable module"

        full_source = inspect.getsource(module)
        tree = ast.parse(full_source)

        found_import = False
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and "model_downloader" in node.module
            ):
                for alias in node.names:
                    if alias.name == "ModelDownloader":
                        found_import = True
                        break

        assert found_import, (
            "sync_service.py must import ModelDownloader from model_downloader module "
            "(e.g. from source_t3k.services.model_downloader import ModelDownloader)"
        )


class TestStageToneCallsDownloader:
    """Verify _stage_tone_models_and_publish calls download_models_for_tone."""

    def test_contains_download_call(self) -> None:
        """_stage_tone_models_and_publish source must contain a call to download_models_for_tone."""
        source = inspect.getsource(T3KSyncService._stage_tone_models_and_publish)
        assert (
            "download_models_for_tone" in source
        ), "_stage_tone_models_and_publish must call download_models_for_tone() after staging models"

    def test_download_call_appears_after_model_staging(self) -> None:
        """download_models_for_tone call must appear after model staging loop."""
        source = inspect.getsource(T3KSyncService._stage_tone_models_and_publish)
        lines = source.splitlines()

        staging_line = None
        download_line = None
        for i, line in enumerate(lines):
            if "session.add" in line.replace("self._", "") and staging_line is None:
                staging_line = i
            if "download_models_for_tone" in line and download_line is None:
                download_line = i

        assert (
            staging_line is not None
        ), "_stage_tone_models_and_publish must stage models via session.add"
        assert (
            download_line is not None
        ), "_stage_tone_models_and_publish must call download_models_for_tone"
        assert download_line > staging_line, (
            "download_models_for_tone must be called AFTER model staging, "
            f"but staging is at line {staging_line} and download is at line {download_line}"
        )


class TestDownloadErrorHandling:
    """Verify download failures don't crash the sync loop."""

    def test_download_call_is_wrapped_in_error_handling(self) -> None:
        """download_models_for_tone call must be wrapped in try/except."""
        source = inspect.getsource(T3KSyncService._stage_tone_models_and_publish)
        dedented = textwrap.dedent(source)
        tree = ast.parse(dedented)

        download_in_try = False

        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                try_source = ast.get_source_segment(dedented, node)
                if try_source and "download_models_for_tone" in try_source:
                    download_in_try = True

        assert download_in_try, (
            "download_models_for_tone call must be wrapped in try/except "
            "so download failures don't crash the sync loop"
        )

    def test_error_handling_catches_exception(self) -> None:
        """Error handler must catch Exception (broad enough for network/IO errors)."""
        source = inspect.getsource(T3KSyncService._stage_tone_models_and_publish)
        dedented = textwrap.dedent(source)
        tree = ast.parse(dedented)

        catches_broad_exception = False

        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                try_source = ast.get_source_segment(dedented, node)
                if try_source and "download_models_for_tone" in try_source:
                    for handler in node.handlers:
                        if handler.type is None or (
                            isinstance(handler.type, ast.Name) and handler.type.id == "Exception"
                        ):
                            catches_broad_exception = True

        assert catches_broad_exception, (
            "Error handling around download_models_for_tone must catch Exception "
            "(broad enough to handle network errors, I/O errors, etc.)"
        )

    def test_error_handling_includes_logging(self) -> None:
        """Download errors should be logged, not silently swallowed."""
        source = inspect.getsource(T3KSyncService._stage_tone_models_and_publish)

        has_logging = (
            "logger" in source.lower()
            or "logging" in source.lower()
            or "log." in source
            or "log(" in source
        )
        assert has_logging, (
            "Download errors must be logged (use logger.error/warning/exception) — "
            "silent swallowing of errors makes debugging impossible"
        )


class TestSyncServiceConstructorAcceptsDownloader:
    """Verify T3KSyncService can be constructed with a ModelDownloader."""

    def test_sync_service_has_downloader_attribute_or_creates_one(self) -> None:
        """T3KSyncService must store or create a ModelDownloader instance."""
        source = inspect.getsource(T3KSyncService)

        has_downloader_ref = (
            "model_downloader" in source.lower()
            or "ModelDownloader" in source
            or "_downloader" in source
        )
        assert has_downloader_ref, (
            "T3KSyncService must reference ModelDownloader — either as a constructor "
            "parameter, stored attribute, or locally instantiated"
        )
