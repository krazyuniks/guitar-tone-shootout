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
        # Parse the AST to check import statements precisely
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


class TestSyncModelsCallsDownloader:
    """Verify sync_models() calls ModelDownloader.download_models_for_pack()."""

    def test_sync_models_contains_download_call(self) -> None:
        """sync_models() source must contain a call to download_models_for_pack."""
        source = inspect.getsource(T3KSyncService.sync_models)
        assert "download_models_for_pack" in source, (
            "sync_models() must call download_models_for_pack() after staging models"
        )

    def test_sync_models_passes_pack_id_to_downloader(self) -> None:
        """sync_models() must pass pack_id to download_models_for_pack."""
        source = inspect.getsource(T3KSyncService.sync_models)
        # The call should include pack_id as argument
        assert "pack_id" in source and "download_models_for_pack" in source, (
            "sync_models() must pass pack_id to download_models_for_pack()"
        )

    def test_download_call_appears_after_model_staging(self) -> None:
        """download_models_for_pack call must appear after model staging loop."""
        source = inspect.getsource(T3KSyncService.sync_models)
        lines = source.splitlines()

        staging_line = None
        download_line = None
        for i, line in enumerate(lines):
            if "session.add" in line.replace("self._", "") and staging_line is None:
                staging_line = i
            if "download_models_for_pack" in line and download_line is None:
                download_line = i

        assert staging_line is not None, "sync_models must stage models via session.add"
        assert download_line is not None, "sync_models must call download_models_for_pack"
        assert download_line > staging_line, (
            "download_models_for_pack must be called AFTER model staging, "
            f"but staging is at line {staging_line} and download is at line {download_line}"
        )


class TestDownloadErrorHandling:
    """Verify download failures don't crash the sync loop."""

    def test_download_call_is_wrapped_in_error_handling(self) -> None:
        """download_models_for_pack call must be wrapped in try/except or contextlib.suppress."""
        source = inspect.getsource(T3KSyncService.sync_models)

        # Parse the AST of the method to find error handling around the download call
        # Dedent the source since it's a method
        dedented = textwrap.dedent(source)
        tree = ast.parse(dedented)

        download_in_try = False
        download_in_suppress = False

        for node in ast.walk(tree):
            # Check for try/except wrapping
            if isinstance(node, ast.Try):
                try_source = ast.get_source_segment(dedented, node)
                if try_source and "download_models_for_pack" in try_source:
                    download_in_try = True

            # Check for contextlib.suppress wrapping
            if isinstance(node, ast.With):
                with_source = ast.get_source_segment(dedented, node)
                if (
                    with_source
                    and "download_models_for_pack" in with_source
                    and "suppress" in with_source
                ):
                    download_in_suppress = True

        assert download_in_try or download_in_suppress, (
            "download_models_for_pack call must be wrapped in try/except or "
            "contextlib.suppress so download failures don't crash the sync loop"
        )

    def test_error_handling_catches_exception(self) -> None:
        """Error handler must catch Exception (not a narrower type that could miss errors)."""
        source = inspect.getsource(T3KSyncService.sync_models)
        dedented = textwrap.dedent(source)
        tree = ast.parse(dedented)

        catches_broad_exception = False

        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                try_source = ast.get_source_segment(dedented, node)
                if try_source and "download_models_for_pack" in try_source:
                    for handler in node.handlers:
                        # except Exception or bare except
                        if handler.type is None or (
                            isinstance(handler.type, ast.Name) and handler.type.id == "Exception"
                        ):
                            catches_broad_exception = True

            # contextlib.suppress(Exception) also counts
            if isinstance(node, ast.With):
                with_source = ast.get_source_segment(dedented, node)
                if (
                    with_source
                    and "download_models_for_pack" in with_source
                    and "suppress" in with_source
                    and "Exception" in with_source
                ):
                    catches_broad_exception = True

        assert catches_broad_exception, (
            "Error handling around download_models_for_pack must catch Exception "
            "(broad enough to handle network errors, I/O errors, etc.)"
        )

    def test_error_handling_includes_logging(self) -> None:
        """Download errors should be logged, not silently swallowed."""
        source = inspect.getsource(T3KSyncService.sync_models)

        # Check the source contains logging in the error handling path
        # Look for logger or logging usage near the download call
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
    """Verify T3KSyncService can be constructed with or receive a ModelDownloader."""

    def test_sync_service_has_downloader_attribute_or_creates_one(self) -> None:
        """T3KSyncService must store or create a ModelDownloader instance."""
        source = inspect.getsource(T3KSyncService)

        # The service should either accept a downloader in __init__ or create one
        has_downloader_ref = (
            "model_downloader" in source.lower()
            or "ModelDownloader" in source
            or "_downloader" in source
        )
        assert has_downloader_ref, (
            "T3KSyncService must reference ModelDownloader — either as a constructor "
            "parameter, stored attribute, or locally instantiated in sync_models()"
        )
