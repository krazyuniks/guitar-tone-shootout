"""Tone3000.com adapter for fetching NAM models and IRs."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path  # noqa: TC003 - used at runtime
from typing import Any

import httpx

from guitar_tone_shootout.domain.models import (
    NAMCapture,
    NAMModelSize,
    NAMModelType,
    NAMTonePack,
)
from guitar_tone_shootout.domain.ports import ModelDownloaderPort, ModelRepositoryPort

logger = logging.getLogger(__name__)

# Tone3000 URL patterns
TONE3000_BASE = "https://www.tone3000.com"
TONE3000_API = "https://api.tone3000.com"
TONE_URL_PATTERN = re.compile(r"tone3000\.com/tones/([a-zA-Z0-9_-]+)")


class Tone3000Error(Exception):
    """Error interacting with Tone3000."""


class Tone3000Adapter(ModelRepositoryPort, ModelDownloaderPort):
    """
    Adapter for Tone3000.com NAM model repository.

    Implements both ModelRepositoryPort (fetching metadata) and
    ModelDownloaderPort (downloading files).
    """

    def __init__(self, timeout: float = 30.0) -> None:
        """Initialize adapter with HTTP client."""
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "GuitarToneShootout/1.0",
                "Accept": "text/html,application/json",
            },
        )

    def __enter__(self) -> Tone3000Adapter:
        return self

    def __exit__(self, *args: object) -> None:
        self._client.close()

    @property
    def source_name(self) -> str:
        """Unique identifier for this source."""
        return "tone3000"

    def fetch_tone_pack(self, page_url: str) -> NAMTonePack:
        """
        Fetch metadata for a tone pack from its page URL.

        Scrapes the Tone3000 page to extract model information.
        """
        slug = self._extract_slug(page_url)
        logger.info(f"Fetching tone pack: {slug}")

        try:
            response = self._client.get(page_url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise Tone3000Error(f"Failed to fetch {page_url}: {e}") from e

        return self._parse_page(response.text, page_url, slug)

    def get_capture_by_name(
        self, page_url: str, capture_name: str
    ) -> tuple[NAMTonePack, NAMCapture]:
        """Fetch a specific capture from a tone pack."""
        tone_pack = self.fetch_tone_pack(page_url)
        capture = tone_pack.get_capture(capture_name)

        if capture is None:
            available = [c.name for c in tone_pack.captures]
            raise ValueError(f"Capture '{capture_name}' not found. Available: {available}")

        return tone_pack, capture

    def download_capture(self, capture: NAMCapture, target_dir: Path) -> Path:
        """Download a NAM capture file."""
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / capture.filename

        if target_path.exists():
            logger.debug(f"Already cached: {target_path}")
            return target_path

        logger.info(f"Downloading: {capture.name}")
        logger.debug(f"URL: {capture.download_url}")

        try:
            response = self._client.get(capture.download_url)
            response.raise_for_status()

            target_path.write_bytes(response.content)
            logger.info(f"Saved: {target_path}")

            return target_path

        except httpx.HTTPError as e:
            raise Tone3000Error(f"Download failed: {e}") from e

    def download_ir(self, url: str, target_path: Path) -> Path:
        """Download an impulse response file."""
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if target_path.exists():
            logger.debug(f"Already cached: {target_path}")
            return target_path

        logger.info(f"Downloading IR: {target_path.name}")

        try:
            response = self._client.get(url)
            response.raise_for_status()

            target_path.write_bytes(response.content)
            return target_path

        except httpx.HTTPError as e:
            raise Tone3000Error(f"IR download failed: {e}") from e

    def _extract_slug(self, url: str) -> str:
        """Extract slug from Tone3000 URL."""
        match = TONE_URL_PATTERN.search(url)
        if not match:
            raise ValueError(f"Invalid Tone3000 URL: {url}")
        return match.group(1)

    def _parse_page(self, html: str, page_url: str, slug: str) -> NAMTonePack:
        """Parse Tone3000 page HTML to extract model data."""
        # Extract Next.js JSON data from script tags
        data = self._extract_nextjs_data(html)

        if data is None:
            raise Tone3000Error("Could not parse page data")

        # Navigate to tone data in the Next.js structure
        tone_data = self._find_tone_data(data)

        if tone_data is None:
            raise Tone3000Error("Could not find tone data in page")

        # Parse captures/models
        captures = self._parse_captures(tone_data)

        # Determine model type
        model_type = self._determine_model_type(tone_data)

        return NAMTonePack(
            source=self.source_name,
            page_url=page_url,
            slug=slug,
            title=tone_data.get("name", slug),
            author=self._extract_author(tone_data),
            model_type=model_type,
            captures=captures,
            description=tone_data.get("description", ""),
            makes=self._extract_list(tone_data, "makes"),
            models=self._extract_list(tone_data, "models"),
            tags=self._extract_list(tone_data, "tags"),
            license=tone_data.get("license", ""),
            downloads=tone_data.get("downloads", 0),
            favorites=tone_data.get("favorites", 0),
        )

    def _extract_nextjs_data(self, html: str) -> dict[str, Any] | None:
        """Extract Next.js __NEXT_DATA__ JSON from page HTML."""
        # Look for Next.js data script
        pattern = r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>'
        match = re.search(pattern, html, re.DOTALL)

        if match:
            try:
                data: Any = json.loads(match.group(1))
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

        # Alternative: Look for inline JSON in React hydration
        # Tone3000 uses various patterns
        json_patterns = [
            r'"tone"\s*:\s*(\{[^}]+\})',
            r'"models"\s*:\s*(\[[^\]]+\])',
        ]

        for pat in json_patterns:
            match = re.search(pat, html)
            if match:
                try:
                    parsed: Any = json.loads(match.group(1))
                    return {"tone": parsed}
                except json.JSONDecodeError:
                    continue

        return None

    def _find_tone_data(self, data: dict[str, Any]) -> dict[str, Any] | None:
        """Navigate Next.js data structure to find tone info."""
        # Try common paths in Next.js data
        paths = [
            ["props", "pageProps", "tone"],
            ["props", "pageProps", "data", "tone"],
            ["tone"],
        ]

        for path in paths:
            current: Any = data
            for key in path:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    current = None
                    break
            if current is not None and isinstance(current, dict):
                # We've verified it's a dict, safe to return
                found_data: dict[str, Any] = current
                return found_data

        # If structured navigation fails, search recursively
        return self._find_dict_with_key(data, "models")

    def _find_dict_with_key(self, obj: Any, key: str) -> dict[str, Any] | None:
        """Recursively find a dict containing a specific key."""
        if isinstance(obj, dict):
            if key in obj:
                return obj
            for value in obj.values():
                result = self._find_dict_with_key(value, key)
                if result is not None:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = self._find_dict_with_key(item, key)
                if result is not None:
                    return result
        return None

    def _parse_captures(self, tone_data: dict[str, Any]) -> list[NAMCapture]:
        """Parse individual captures from tone data."""
        captures = []
        models = tone_data.get("models", [])

        for model in models:
            if not isinstance(model, dict):
                continue

            # Extract model URL
            model_url = model.get("model_url", "")
            if not model_url:
                continue

            # Parse size enum
            size_str = model.get("size", "standard").lower()
            try:
                size = NAMModelSize(size_str)
            except ValueError:
                size = NAMModelSize.STANDARD

            capture = NAMCapture(
                name=model.get("name", "Unknown"),
                download_url=model_url,
                esr=float(model.get("esr", 0)),
                epochs=int(model.get("epochs", 0)),
                size=size,
                sweep_signal=model.get("sweep_signal", "standard"),
                training_status=model.get("training_status", "unknown"),
            )
            captures.append(capture)

        return captures

    def _determine_model_type(self, tone_data: dict[str, Any]) -> NAMModelType:
        """Determine the type of NAM model from metadata."""
        gear_type = tone_data.get("gear_type", "").lower()
        category = tone_data.get("category", "").lower()

        if "full rig" in gear_type or "full_rig" in category:
            return NAMModelType.FULL_RIG
        elif "pedal" in gear_type:
            return NAMModelType.PEDAL
        elif "combo" in gear_type:
            return NAMModelType.AMP_COMBO
        elif "amp" in gear_type or "head" in gear_type:
            return NAMModelType.AMP_HEAD

        return NAMModelType.UNKNOWN

    def _extract_author(self, tone_data: dict[str, Any]) -> str:
        """Extract author/uploader from tone data."""
        # Try various paths
        if "user" in tone_data and isinstance(tone_data["user"], dict):
            username = tone_data["user"].get("username", "Unknown")
            return str(username) if username else "Unknown"
        if "author" in tone_data:
            return str(tone_data["author"])
        if "uploader" in tone_data:
            return str(tone_data["uploader"])
        return "Unknown"

    def _extract_list(self, data: dict[str, Any], key: str) -> list[str]:
        """Safely extract a list of strings from data."""
        value = data.get(key, [])
        if isinstance(value, list):
            return [str(v) for v in value if v]
        return []


def get_adapter() -> Tone3000Adapter:
    """Factory function to create Tone3000 adapter."""
    return Tone3000Adapter()
