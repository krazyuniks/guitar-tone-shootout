"""Job page handlers — list, detail, status fragment."""

from html import escape
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gts.domain.value_objects.job_status import JobStatus
from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.user import User
from webapp.api.pages.context import job_to_context
from webapp.auth.dependencies import (
    get_current_user_page,
    get_current_user_required,
    get_db_session,
)
from webapp.templates import templates

router = APIRouter(tags=["pages"])


@router.get("/jobs", response_class=HTMLResponse)
async def jobs_list_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_page)],
) -> HTMLResponse:
    """Render jobs list page showing user's active and recent jobs."""
    from webapp.services.job_service import JobService

    service = JobService(db)
    jobs = await service.get_by_user_id(current_user.id, limit=50)

    job_items = [job_to_context(job) for job in jobs]

    return templates.TemplateResponse(
        request,
        "pages/jobs.html",
        {
            "jobs": job_items,
            "user": current_user,
        },
    )


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail_page(
    request: Request,
    job_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_page)],
) -> HTMLResponse:
    """Render job detail page with progress display."""
    from webapp.services.job_service import JobService

    service = JobService(db)
    job = await service.get_by_id(UUID(job_id), current_user.id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    return templates.TemplateResponse(
        request,
        "pages/job_detail.html",
        {
            "job": job_to_context(job),
            "user": current_user,
        },
    )


@router.get("/jobs/{job_id}/status", response_class=HTMLResponse)
async def job_status_fragment(
    job_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> HTMLResponse:
    """Render an HTMX fragment with current job status for the owner."""
    stmt = select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    status_value = job.status.value if hasattr(job.status, "value") else str(job.status)
    should_poll = job.status in JobStatus.active_states()
    message = escape(job.message or "")
    error = escape(job.error or "")
    job_type = escape(job.job_type.value if hasattr(job.job_type, "value") else str(job.job_type))

    html = [
        '<div class="container mx-auto px-4 py-8 max-w-2xl">',
        '<div class="bg-[var(--color-bg-surface)] rounded-lg border border-[var(--border)] p-6" '
        f'data-polling="{str(should_poll).lower()}">',
        f'<h1 class="text-xl font-semibold text-[var(--color-text-primary)] mb-2">Job {escape(str(job.id))}</h1>',
        f'<p class="text-sm text-[var(--color-text-secondary)] mb-1">Type: {job_type}</p>',
        f'<p class="text-sm text-[var(--color-text-secondary)] mb-1">Status: {escape(status_value)}</p>',
        f'<p class="text-sm text-[var(--color-text-secondary)] mb-4">Progress: {job.progress}%</p>',
    ]

    if message:
        html.append(
            f'<p class="text-sm text-[var(--color-text-primary)] mb-2" data-testid="job-message">{message}</p>'
        )
    if error:
        html.append(f'<p class="text-sm text-red-400" data-testid="job-error">Error: {error}</p>')

    html.append("</div></div>")
    return HTMLResponse(content="".join(html), status_code=status.HTTP_200_OK)
