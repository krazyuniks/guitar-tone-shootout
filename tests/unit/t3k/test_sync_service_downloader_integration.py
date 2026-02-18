"""Unit tests for ModelDownloader integration into sync_service.

Verifies that sync_service.py imports and calls ModelDownloader, and that
download calls are wrapped with error handling so failures don't crash
the sync batch.

Uses inspect.getsource() for static source analysis — this is a wiring task,
not a behaviour test.
"""

import ast
import inspect
import textwrap

from source_t3k.services.sync_service import T3KSyncService


class TestSyncServiceImportsModelDownloader:
    """Verify sync_service.py imports ModelDownloader."""

    def test_sync_service_module_imports_model_downloader(self) -> None:
        module_source = inspect.getmodule(T3KSyncService)
        assert module_source is not None
        full_source = inspect.getsource(module_source)
        assert "ModelDownloader" in full_source

    def test_sync_service_module_imports_from_correct_module(self) -> None:
        module = inspect.getmodule(T3KSyncService)
        assert module is not None
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

        assert found_import


class TestProcessNewToneCallsDownloader:
    """Verify _process_new_tone calls download logic."""

    def test_contains_download_call(self) -> None:
        source = inspect.getsource(T3KSyncService._process_new_tone)
        assert "_try_download" in source or "download_model" in source

    def test_download_call_appears_after_model_upsert(self) -> None:
        source = inspect.getsource(T3KSyncService._process_new_tone)
        lines = source.splitlines()

        upsert_line = None
        download_line = None
        for i, line in enumerate(lines):
            if "_upsert_model" in line and upsert_line is None:
                upsert_line = i
            if "_try_download" in line and download_line is None:
                download_line = i

        assert upsert_line is not None
        assert download_line is not None
        assert download_line > upsert_line


class TestDownloadErrorHandling:
    """Verify download failures don't crash the sync batch."""

    def test_try_download_is_wrapped_in_error_handling(self) -> None:
        source = inspect.getsource(T3KSyncService._try_download)
        dedented = textwrap.dedent(source)
        tree = ast.parse(dedented)

        download_in_try = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                try_source = ast.get_source_segment(dedented, node)
                if try_source and "download_model" in try_source:
                    download_in_try = True

        assert download_in_try

    def test_error_handling_catches_exception(self) -> None:
        source = inspect.getsource(T3KSyncService._try_download)
        dedented = textwrap.dedent(source)
        tree = ast.parse(dedented)

        catches_broad_exception = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                try_source = ast.get_source_segment(dedented, node)
                if try_source and "download_model" in try_source:
                    for handler in node.handlers:
                        if handler.type is None or (
                            isinstance(handler.type, ast.Name) and handler.type.id == "Exception"
                        ):
                            catches_broad_exception = True

        assert catches_broad_exception

    def test_error_handling_includes_logging(self) -> None:
        source = inspect.getsource(T3KSyncService._try_download)
        has_logging = "logger" in source.lower() or "logging" in source.lower()
        assert has_logging


class TestSyncServiceConstructorAcceptsDownloader:
    """Verify T3KSyncService can be constructed with a ModelDownloader."""

    def test_sync_service_has_downloader_attribute(self) -> None:
        source = inspect.getsource(T3KSyncService)
        has_downloader_ref = (
            "model_downloader" in source.lower()
            or "ModelDownloader" in source
            or "_downloader" in source
        )
        assert has_downloader_ref
