"""Sitemap handler — sitemap.xml generation."""

import os
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.shootout import Shootout, ShootoutStatus
from webapp.auth.dependencies import get_db_session

router = APIRouter(tags=["pages"])


@router.get("/sitemap.xml", response_class=Response)
async def sitemap_xml(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """Generate dynamic sitemap.xml for search engines."""
    public_url = os.getenv("PUBLIC_URL", "http://testserver")

    now = datetime.now(UTC)
    static_pages = [
        ("/", "daily", "1.0", now),
        ("/about", "monthly", "0.5", now),
        ("/gear", "daily", "0.9", now),
        ("/shootouts", "daily", "0.8", now),
    ]

    gear_result = await db.execute(
        select(Gear).where(Gear.is_public.is_(True)).order_by(Gear.updated_at.desc())
    )
    public_gear = gear_result.scalars().all()

    shootout_result = await db.execute(
        select(Shootout)
        .where(Shootout.status == ShootoutStatus.COMPLETED)
        .order_by(Shootout.updated_at.desc())
    )
    completed_shootouts = shootout_result.scalars().all()

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    for path, changefreq, priority, lastmod in static_pages:
        xml_lines.extend(
            [
                "  <url>",
                f"    <loc>{public_url}{path}</loc>",
                f"    <lastmod>{lastmod.isoformat()}</lastmod>",
                f"    <changefreq>{changefreq}</changefreq>",
                f"    <priority>{priority}</priority>",
                "  </url>",
            ]
        )

    for gear in public_gear:
        lastmod = gear.updated_at if gear.updated_at else gear.created_at
        xml_lines.extend(
            [
                "  <url>",
                f"    <loc>{public_url}/gear/{gear.slug}</loc>",
                f"    <lastmod>{lastmod.isoformat()}</lastmod>",
                "    <changefreq>weekly</changefreq>",
                "    <priority>0.7</priority>",
                "  </url>",
            ]
        )

    for shootout in completed_shootouts:
        lastmod = shootout.updated_at if shootout.updated_at else shootout.created_at
        xml_lines.extend(
            [
                "  <url>",
                f"    <loc>{public_url}/shootouts/{shootout.id}</loc>",
                f"    <lastmod>{lastmod.isoformat()}</lastmod>",
                "    <changefreq>weekly</changefreq>",
                "    <priority>0.6</priority>",
                "  </url>",
            ]
        )

    xml_lines.append("</urlset>")
    xml_content = "\n".join(xml_lines)

    return Response(content=xml_content, media_type="application/xml")
