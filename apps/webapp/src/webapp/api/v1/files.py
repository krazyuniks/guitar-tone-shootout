"""File serving API with HMAC-signed URLs.

Streams files with signature validation, range header support,
and path traversal protection.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import FileResponse

from webapp.config.uploads import get_secret_key, get_upload_base
from webapp.services.asset_service import AssetService

router = APIRouter(prefix="/api/files", tags=["files"])


def _get_asset_service() -> AssetService:
    """Get AssetService instance with production config.

    Returns:
        Configured AssetService instance
    """
    secret_key = get_secret_key()
    upload_base = get_upload_base()
    return AssetService(secret_key=secret_key, upload_base=upload_base)


@router.get("/{signature}", response_model=None)
async def serve_file(signature: str, request: Request) -> FileResponse | Response:
    """Stream a file using HMAC-signed URL.

    Validates signature, checks ownership, and streams file with
    correct Content-Type. Supports Range headers for partial content.

    Args:
        signature: Base64-encoded HMAC signature
        request: FastAPI request object (for Range header)

    Returns:
        FileResponse with file content (or Response for partial content)

    Raises:
        HTTPException: 404 if signature invalid/expired or file not found
    """
    service = _get_asset_service()

    # Resolve and validate file path
    file_path = service.resolve_file_path(signature)
    if not file_path:
        # Return 404 for any validation failure (no existence leaking)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Get content type
    content_type = service.get_content_type(str(file_path))

    # Check for Range header to support partial content
    range_header = request.headers.get("range")
    if range_header:
        # Parse Range header (format: "bytes=start-end")
        return _serve_range_request(file_path, range_header, content_type)

    # Return full file
    return FileResponse(
        path=file_path,
        media_type=content_type,
        filename=file_path.name,
    )


def _serve_range_request(
    file_path: Path,
    range_header: str,
    content_type: str,
) -> FileResponse | Response:
    """Serve a partial content response for Range requests.

    Args:
        file_path: Path to file
        range_header: Range header value (e.g., "bytes=0-99")
        content_type: MIME type for Content-Type header

    Returns:
        Response with 206 Partial Content, or FileResponse on error
    """
    # Parse range header
    try:
        range_spec = range_header.replace("bytes=", "")
        start_str, end_str = range_spec.split("-")
        start = int(start_str) if start_str else 0
        file_size = file_path.stat().st_size
        end = int(end_str) if end_str else file_size - 1

        # Clamp to file bounds
        start = max(0, min(start, file_size - 1))
        end = max(start, min(end, file_size - 1))

        # Read the range
        with file_path.open("rb") as f:
            f.seek(start)
            chunk = f.read(end - start + 1)

        # Create response with 206 status
        return Response(
            content=chunk,
            status_code=206,
            media_type=content_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(len(chunk)),
            },
        )

    except (ValueError, OSError):
        # Invalid range, return full file instead
        return FileResponse(
            path=file_path,
            media_type=content_type,
            filename=file_path.name,
        )
