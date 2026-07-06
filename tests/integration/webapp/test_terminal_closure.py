"""Reconciliation terminal closure and the transition service (ADR-0005).

The adversarial shapes here are the pre-fix strand class: a CANCELLED or
DEAD_LETTERED child under a PROCESSING parent used to land in neither the
all-complete nor the any-failed branch, stranding the shootout in PROCESSING
forever. Closed counting makes every terminal child land in exactly one bucket.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from gts.domain.value_objects.job_status import JobStatus, JobType
from messaging.pgmq_client import PgmqClient
from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.shootout import Shootout, ShootoutStatus
from webapp.adapters.persistence.models.user import User
from webapp.services.job_transitions import (
    InvalidTransitionError,
    reconcile_parent,
    transition_job,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(autouse=True)
async def _queues(db_session: AsyncSession) -> None:
    """Reconcile enqueues the master job through the real outbox."""
    await PgmqClient(db_session).create_queue("audio_commands")


@pytest.fixture
async def shootout_tree(db_session: AsyncSession, test_user: User) -> dict:
    """A PROCESSING shootout with a RUNNING parent job and three audio children."""
    shootout = Shootout(
        id=uuid4(),
        user_id=test_user.id,
        name="Closure Shootout",
        status=ShootoutStatus.PROCESSING,
    )
    db_session.add(shootout)

    parent = Job(
        id=uuid4(),
        user_id=test_user.id,
        job_type=JobType.SHOOTOUT,
        entity_id=shootout.id,
        status=JobStatus.RUNNING,
        progress=0,
    )
    db_session.add(parent)

    children = []
    for _ in range(3):
        child = Job(
            id=uuid4(),
            user_id=test_user.id,
            job_type=JobType.SHOOTOUT_AUDIO,
            parent_job_id=parent.id,
            entity_id=uuid4(),
            status=JobStatus.RUNNING,
            progress=0,
        )
        db_session.add(child)
        children.append(child)

    await db_session.flush()
    return {"shootout": shootout, "parent": parent, "children": children}


async def _set_status(db_session: AsyncSession, job: Job, status: JobStatus) -> None:
    """Test scaffolding: place a child in a precondition state directly."""
    await db_session.execute(
        text("UPDATE core_jobs SET status = :status WHERE id = :id"),
        {"status": status.value, "id": str(job.id)},
    )
    db_session.expire(job)


@pytest.mark.asyncio
@pytest.mark.integration
class TestClosedReconciliation:
    @pytest.mark.parametrize(
        "stranding_status",
        [JobStatus.CANCELLED, JobStatus.DEAD_LETTERED, JobStatus.FAILED],
    )
    async def test_any_failed_class_child_projects_shootout_failed(
        self,
        db_session: AsyncSession,
        shootout_tree: dict,
        stranding_status: JobStatus,
    ) -> None:
        """The strand class: one terminal-without-success child fails the run."""
        parent = shootout_tree["parent"]
        children = shootout_tree["children"]
        await _set_status(db_session, children[0], JobStatus.COMPLETED)
        await _set_status(db_session, children[1], JobStatus.COMPLETED)
        await _set_status(db_session, children[2], stranding_status)

        await reconcile_parent(db_session, parent.id)
        await db_session.commit()

        await db_session.refresh(parent)
        await db_session.refresh(shootout_tree["shootout"])
        assert parent.status == JobStatus.FAILED
        assert shootout_tree["shootout"].status == ShootoutStatus.FAILED
        assert stranding_status.value in (parent.error or "")

    async def test_all_completed_spawns_and_enqueues_master(
        self,
        db_session: AsyncSession,
        shootout_tree: dict,
    ) -> None:
        parent = shootout_tree["parent"]
        for child in shootout_tree["children"]:
            await _set_status(db_session, child, JobStatus.COMPLETED)

        await reconcile_parent(db_session, parent.id)
        await db_session.commit()

        master = (
            await db_session.execute(
                select(Job).where(
                    Job.parent_job_id == parent.id,
                    Job.job_type == JobType.SHOOTOUT_MASTER,
                )
            )
        ).scalar_one()
        assert master.status == JobStatus.QUEUED

        result = await db_session.execute(
            text(
                "SELECT message FROM pgmq.q_audio_commands "
                "WHERE message->'payload'->>'job_id' = :jid"
            ),
            {"jid": str(master.id)},
        )
        assert len(result.fetchall()) == 1

    async def test_incomplete_children_keep_processing(
        self,
        db_session: AsyncSession,
        shootout_tree: dict,
    ) -> None:
        """No terminal-failure child and unfinished work: still PROCESSING."""
        parent = shootout_tree["parent"]
        await _set_status(db_session, shootout_tree["children"][0], JobStatus.COMPLETED)

        await reconcile_parent(db_session, parent.id)
        await db_session.commit()

        await db_session.refresh(parent)
        await db_session.refresh(shootout_tree["shootout"])
        assert parent.status == JobStatus.RUNNING
        assert shootout_tree["shootout"].status == ShootoutStatus.PROCESSING


@pytest.mark.asyncio
@pytest.mark.integration
class TestTransitionService:
    async def test_terminal_child_transition_reconciles_parent(
        self,
        db_session: AsyncSession,
        shootout_tree: dict,
    ) -> None:
        """One call moves the child and re-projects the parent atomically."""
        parent = shootout_tree["parent"]
        children = shootout_tree["children"]
        await _set_status(db_session, children[0], JobStatus.COMPLETED)
        await _set_status(db_session, children[1], JobStatus.COMPLETED)

        await transition_job(db_session, children[2].id, JobStatus.FAILED, error="render exploded")

        await db_session.refresh(parent)
        await db_session.refresh(shootout_tree["shootout"])
        assert parent.status == JobStatus.FAILED
        assert shootout_tree["shootout"].status == ShootoutStatus.FAILED

        await db_session.refresh(children[2])
        assert children[2].status == JobStatus.FAILED
        assert children[2].error == "render exploded"
        assert children[2].completed_at is not None

    async def test_invalid_transition_is_rejected_without_writes(
        self,
        db_session: AsyncSession,
        shootout_tree: dict,
    ) -> None:
        child = shootout_tree["children"][0]
        await _set_status(db_session, child, JobStatus.COMPLETED)

        with pytest.raises(InvalidTransitionError):
            await transition_job(db_session, child.id, JobStatus.RUNNING)

        await db_session.refresh(child)
        assert child.status == JobStatus.COMPLETED

    async def test_published_shootout_never_regresses(
        self,
        db_session: AsyncSession,
        shootout_tree: dict,
    ) -> None:
        """Terminal-per-generation: a COMPLETED shootout stays COMPLETED."""
        shootout = shootout_tree["shootout"]
        await db_session.execute(
            text("UPDATE core_shootouts SET status = :status WHERE id = :id"),
            {"status": ShootoutStatus.COMPLETED.value, "id": str(shootout.id)},
        )
        db_session.expire(shootout)
        await _set_status(db_session, shootout_tree["children"][0], JobStatus.DEAD_LETTERED)

        await reconcile_parent(db_session, shootout_tree["parent"].id)
        await db_session.commit()

        await db_session.refresh(shootout)
        assert shootout.status == ShootoutStatus.COMPLETED
