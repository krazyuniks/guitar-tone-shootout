"""Settings page handlers — account settings."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_identity import UserIdentity
from webapp.auth.dependencies import get_current_user_page, get_db_session
from webapp.templates import templates

router = APIRouter(tags=["pages"])


@router.get("/settings/account", response_class=HTMLResponse)
async def settings_account_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_page)],
) -> HTMLResponse:
    """Render account settings page with linked provider status."""
    result = await db.execute(
        select(User)
        .where(User.id == current_user.id)
        .options(joinedload(User.identities).joinedload(UserIdentity.provider))
    )
    user_with_identities = result.unique().scalar_one_or_none()

    identities = user_with_identities.identities if user_with_identities else []
    linked_providers = {
        identity.provider.name: identity for identity in identities if identity.provider
    }

    provider_defs = [
        ("t3k", "Tone3000", True),
        ("google", "Google", False),
        ("github", "GitHub", False),
        ("facebook", "Facebook", False),
    ]

    providers = []
    for name, display_name, available in provider_defs:
        identity = linked_providers.get(name)
        providers.append(
            {
                "name": name,
                "display_name": display_name,
                "available": available,
                "linked": identity is not None,
                "username": identity.username if identity else None,
                "is_last_provider": len(linked_providers) <= 1 and identity is not None,
            }
        )

    return templates.TemplateResponse(
        request,
        "pages/settings_account.html",
        {
            "user": current_user,
            "providers": providers,
        },
    )
