"""Test/debug endpoints for triggering various exception types.

These endpoints are only available when ENV=development and are used by E2E tests
to verify error handling works end-to-end. No authentication required.
"""

from fastapi import APIRouter

from webapp.exceptions import BadRequestError, ConflictError, NotFoundError, ValidationError

router = APIRouter(prefix="/api/test")


@router.get("/error/404")
async def trigger_404() -> None:
    """Trigger a NotFoundError (404).

    Raises:
        NotFoundError: Always raises to test 404 error handling.
    """
    raise NotFoundError(message="Test 404 error triggered")


@router.get("/error/400")
async def trigger_400() -> None:
    """Trigger a BadRequestError (400).

    Raises:
        BadRequestError: Always raises to test 400 error handling.
    """
    raise BadRequestError(message="Test 400 error triggered")


@router.get("/error/409")
async def trigger_409() -> None:
    """Trigger a ConflictError (409).

    Raises:
        ConflictError: Always raises to test 409 error handling.
    """
    raise ConflictError(message="Test 409 error triggered")


@router.get("/error/422")
async def trigger_422() -> None:
    """Trigger a ValidationError (422).

    Raises:
        ValidationError: Always raises to test 422 error handling.
    """
    raise ValidationError(message="Test 422 error triggered")


@router.get("/error/500")
async def trigger_500() -> None:
    """Trigger an unhandled exception (500).

    Raises:
        RuntimeError: Always raises to test 500 error handling.
    """
    raise RuntimeError("Test 500 error triggered")
