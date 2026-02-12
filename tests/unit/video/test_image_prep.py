"""Unit tests for video image preparation utilities."""

from io import BytesIO
from pathlib import Path

from PIL import Image

from video.image_prep import (
    convert_to_format,
    normalize_gear_image,
    resize_image,
)


class TestResizeImage:
    """Tests for image resizing."""

    def test_resizes_to_target_dimensions(self) -> None:
        """Resize maintains aspect ratio and fits within target size."""
        # Create a 200x100 test image (2:1 aspect ratio)
        img = Image.new("RGB", (200, 100), color="red")

        resized = resize_image(img, width=100, height=100)

        # Should be 100x50 (maintains 2:1 aspect, fits in 100x100)
        assert resized.width == 100
        assert resized.height == 50

    def test_resizes_tall_image(self) -> None:
        """Resize handles tall (portrait) images."""
        # Create a 100x200 test image (1:2 aspect ratio)
        img = Image.new("RGB", (100, 200), color="blue")

        resized = resize_image(img, width=100, height=100)

        # Should be 50x100 (maintains 1:2 aspect, fits in 100x100)
        assert resized.width == 50
        assert resized.height == 100

    def test_does_not_upscale_smaller_images(self) -> None:
        """Resize does not upscale images smaller than target."""
        img = Image.new("RGB", (50, 50), color="green")

        resized = resize_image(img, width=200, height=200)

        # Should remain 50x50 (no upscaling)
        assert resized.width == 50
        assert resized.height == 50


class TestConvertToFormat:
    """Tests for image format conversion."""

    def test_converts_png_to_jpeg(self) -> None:
        """Convert changes image format."""
        img = Image.new("RGB", (100, 100), color="red")

        converted = convert_to_format(img, target_format="JPEG")

        # Verify format changed
        buffer = BytesIO()
        converted.save(buffer, format="JPEG")
        buffer.seek(0)
        reloaded = Image.open(buffer)
        assert reloaded.format == "JPEG"

    def test_converts_jpeg_to_png(self) -> None:
        """Convert handles JPEG to PNG."""
        img = Image.new("RGB", (100, 100), color="blue")

        converted = convert_to_format(img, target_format="PNG")

        buffer = BytesIO()
        converted.save(buffer, format="PNG")
        buffer.seek(0)
        reloaded = Image.open(buffer)
        assert reloaded.format == "PNG"

    def test_preserves_dimensions_during_conversion(self) -> None:
        """Format conversion does not change image dimensions."""
        img = Image.new("RGB", (123, 456), color="green")

        converted = convert_to_format(img, target_format="PNG")

        assert converted.width == 123
        assert converted.height == 456


class TestNormalizeGearImage:
    """Tests for gear image normalization pipeline."""

    def test_normalizes_gear_image_path(self, tmp_path: Path) -> None:
        """Normalize processes image file to standard format."""
        # Create a test image
        test_img = Image.new("RGB", (300, 200), color="red")
        input_path = tmp_path / "gear.png"
        test_img.save(input_path)

        output_path = normalize_gear_image(
            input_path=str(input_path),
            output_dir=str(tmp_path / "output"),
            target_width=150,
            target_height=150,
            target_format="JPEG",
        )

        # Verify output exists
        assert Path(output_path).exists()

        # Verify output image properties
        output_img = Image.open(output_path)
        assert output_img.format == "JPEG"
        # Should be 150x100 (maintains 3:2 aspect, fits in 150x150)
        assert output_img.width == 150
        assert output_img.height == 100

    def test_creates_output_directory_if_missing(self, tmp_path: Path) -> None:
        """Normalize creates output directory if it doesn't exist."""
        test_img = Image.new("RGB", (100, 100), color="blue")
        input_path = tmp_path / "gear.jpg"
        test_img.save(input_path)

        output_dir = tmp_path / "nested" / "output"
        assert not output_dir.exists()

        output_path = normalize_gear_image(
            input_path=str(input_path),
            output_dir=str(output_dir),
            target_width=50,
            target_height=50,
        )

        assert output_dir.exists()
        assert Path(output_path).exists()

    def test_handles_rgba_images_with_transparency(self, tmp_path: Path) -> None:
        """Normalize converts RGBA to RGB for JPEG compatibility."""
        # Create RGBA image (PNG with alpha channel)
        test_img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        input_path = tmp_path / "transparent.png"
        test_img.save(input_path)

        output_path = normalize_gear_image(
            input_path=str(input_path),
            output_dir=str(tmp_path / "output"),
            target_format="JPEG",
        )

        output_img = Image.open(output_path)
        # JPEG does not support alpha channel
        assert output_img.mode == "RGB"
        assert output_img.format == "JPEG"
