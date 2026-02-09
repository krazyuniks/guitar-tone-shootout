"""Image preparation utilities for video composition.

Normalises gear images for Remotion compositions using Pillow:
- Resize to standard dimensions
- Format conversion (JPEG, PNG)
- Quality optimisation
"""

from io import BytesIO
from pathlib import Path
from typing import Literal

from PIL import Image


ImageFormat = Literal["JPEG", "PNG", "WEBP"]


def resize_image(
    img: Image.Image,
    width: int,
    height: int,
) -> Image.Image:
    """Resize image to fit within target dimensions while maintaining aspect ratio.

    Does not upscale images smaller than target dimensions.

    Args:
        img: PIL Image to resize
        width: Maximum width in pixels
        height: Maximum height in pixels

    Returns:
        Resized PIL Image (maintains aspect ratio)
    """
    # Don't upscale smaller images
    if img.width <= width and img.height <= height:
        return img

    # Calculate new dimensions maintaining aspect ratio
    img_copy = img.copy()
    img_copy.thumbnail((width, height), Image.Resampling.LANCZOS)
    return img_copy


def convert_to_format(
    img: Image.Image,
    target_format: ImageFormat,
) -> Image.Image:
    """Convert image to target format.

    Handles RGBA to RGB conversion for JPEG compatibility.

    Args:
        img: PIL Image to convert
        target_format: Target format (JPEG, PNG, WEBP)

    Returns:
        Converted PIL Image
    """
    # Convert RGBA to RGB if saving as JPEG
    if target_format == "JPEG" and img.mode == "RGBA":
        rgb_img = Image.new("RGB", img.size, (255, 255, 255))
        rgb_img.paste(img, mask=img.split()[3])
        return rgb_img

    return img


def normalize_gear_image(
    input_path: str,
    output_dir: str,
    target_width: int = 1920,
    target_height: int = 1080,
    target_format: ImageFormat = "JPEG",
    quality: int = 85,
) -> str:
    """Normalize gear image for video composition.

    Resizes, converts format, and optimizes quality. Creates output directory if needed.

    Args:
        input_path: Path to source image
        output_dir: Directory to save normalized image
        target_width: Maximum width in pixels
        target_height: Maximum height in pixels
        target_format: Output format (JPEG, PNG, WEBP)
        quality: Compression quality (1-100, JPEG/WEBP only)

    Returns:
        Path to normalized image file

    Raises:
        FileNotFoundError: If input_path does not exist
        ValueError: If image cannot be opened or format is invalid
    """
    input_p = Path(input_path)
    if not input_p.exists():
        raise FileNotFoundError(f"Image not found: {input_path}")

    try:
        with Image.open(input_p) as img:
            # Resize to fit within target dimensions
            resized = resize_image(img, target_width, target_height)

            # Convert to target format
            converted = convert_to_format(resized, target_format)

            # Generate output path
            output_dir_p = Path(output_dir)
            output_dir_p.mkdir(parents=True, exist_ok=True)

            ext = target_format.lower()
            if ext == "jpeg":
                ext = "jpg"
            output_path = output_dir_p / f"{input_p.stem}.{ext}"

            # Save with format-specific options
            save_kwargs = {"format": target_format}
            if target_format in ("JPEG", "WEBP"):
                save_kwargs["quality"] = quality
                save_kwargs["optimize"] = True

            converted.save(output_path, **save_kwargs)
            return str(output_path)

    except Exception as e:
        raise ValueError(f"Failed to process image {input_path}: {e}") from e


def normalise_image(
    input_path: Path,
    output_path: Path,
    max_width: int = 1920,
    max_height: int = 1080,
    format: ImageFormat = "JPEG",
    quality: int = 85,
) -> None:
    """Normalise an image for video composition.

    Args:
        input_path: Path to source image
        output_path: Path to save normalised image
        max_width: Maximum width in pixels
        max_height: Maximum height in pixels
        format: Output format (JPEG, PNG, WEBP)
        quality: Compression quality (1-100, JPEG/WEBP only)

    Raises:
        FileNotFoundError: If input_path does not exist
        ValueError: If image cannot be opened or format is invalid
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Image not found: {input_path}")

    try:
        with Image.open(input_path) as img:
            # Convert RGBA to RGB if saving as JPEG
            if format == "JPEG" and img.mode == "RGBA":
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[3])
                img = rgb_img

            # Resize if image exceeds max dimensions
            if img.width > max_width or img.height > max_height:
                img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

            # Save with format-specific options
            save_kwargs = {"format": format}
            if format in ("JPEG", "WEBP"):
                save_kwargs["quality"] = quality
                save_kwargs["optimize"] = True

            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, **save_kwargs)

    except Exception as e:
        raise ValueError(f"Failed to process image {input_path}: {e}") from e


def normalise_image_bytes(
    image_data: bytes,
    max_width: int = 1920,
    max_height: int = 1080,
    format: ImageFormat = "JPEG",
    quality: int = 85,
) -> bytes:
    """Normalise image from bytes, return normalised bytes.

    Args:
        image_data: Source image as bytes
        max_width: Maximum width in pixels
        max_height: Maximum height in pixels
        format: Output format (JPEG, PNG, WEBP)
        quality: Compression quality (1-100, JPEG/WEBP only)

    Returns:
        Normalised image as bytes

    Raises:
        ValueError: If image cannot be opened or format is invalid
    """
    try:
        with Image.open(BytesIO(image_data)) as img:
            # Convert RGBA to RGB if saving as JPEG
            if format == "JPEG" and img.mode == "RGBA":
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[3])
                img = rgb_img

            # Resize if image exceeds max dimensions
            if img.width > max_width or img.height > max_height:
                img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

            # Save to BytesIO
            output = BytesIO()
            save_kwargs = {"format": format}
            if format in ("JPEG", "WEBP"):
                save_kwargs["quality"] = quality
                save_kwargs["optimize"] = True

            img.save(output, **save_kwargs)
            return output.getvalue()

    except Exception as e:
        raise ValueError(f"Failed to process image data: {e}") from e
