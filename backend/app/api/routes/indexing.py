"""Indexing API endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_graph
from app.core.knowledge.graph_manager import KnowledgeGraphManager
from app.db.session import get_db
from app.models.database import (
    AuditLog,
    IndexingJob,
    Project,
    User,
    user_organizations,
)
from app.models.enums import AuditAction, IndexingJobType, ScanStatus
from app.models.schemas import IndexingJobResponse

router = APIRouter(tags=["indexing"])


# ---- helpers ----


async def _verify_project_access(
    project_id: uuid.UUID, user: User, db: AsyncSession
) -> Project:
    """Verify user has access to the project and return it."""
    result = await db.execute(
        select(user_organizations.c.org_id).where(
            user_organizations.c.user_id == user.id
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no organization",
        )

    proj_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.org_id == row.org_id)
    )
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project


async def _check_no_running_job(
    project_id: uuid.UUID, db: AsyncSession
) -> None:
    """Prevent concurrent indexing jobs on the same project."""
    result = await db.execute(
        select(IndexingJob).where(
            IndexingJob.project_id == project_id,
            IndexingJob.status.in_([ScanStatus.PENDING, ScanStatus.RUNNING]),
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An indexing job is already running for this project",
        )


async def _create_and_dispatch_job(
    project: Project,
    job_type: IndexingJobType,
    user: User,
    db: AsyncSession,
) -> IndexingJob:
    """Create an IndexingJob record, dispatch Celery task, write audit log."""
    if not project.root_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no root_path configured",
        )

    job = IndexingJob(
        id=uuid.uuid4(),
        project_id=project.id,
        status=ScanStatus.PENDING,
        job_type=job_type,
    )
    db.add(job)

    audit = AuditLog(
        id=uuid.uuid4(),
        project_id=project.id,
        user_id=user.id,
        action=AuditAction.INDEX_STARTED,
        details={"job_id": str(job.id), "job_type": job_type.value},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(job)

    # Dispatch Celery task (lazy import to avoid loading Celery in API process)
    from app.workers.indexing_tasks import run_indexing_job

    run_indexing_job.delay(
        project_id=str(project.id),
        root_path=project.root_path,
        job_id=str(job.id),
        job_type=job_type.value,
    )

    return job


# ---- endpoints ----


@router.post(
    "/projects/{project_id}/index",
    response_model=IndexingJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_full_index(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a full re-index of a project's codebase."""
    project = await _verify_project_access(project_id, current_user, db)
    await _check_no_running_job(project_id, db)
    job = await _create_and_dispatch_job(
        project, IndexingJobType.FULL, current_user, db
    )
    return IndexingJobResponse.model_validate(job)


@router.post(
    "/projects/{project_id}/index/incremental",
    response_model=IndexingJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_incremental_index(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger an incremental index (only changed/new files)."""
    project = await _verify_project_access(project_id, current_user, db)
    await _check_no_running_job(project_id, db)
    job = await _create_and_dispatch_job(
        project, IndexingJobType.INCREMENTAL, current_user, db
    )
    return IndexingJobResponse.model_validate(job)


@router.get(
    "/projects/{project_id}/index/status",
    response_model=IndexingJobResponse,
)
async def get_indexing_status(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the most recent indexing job status for a project."""
    await _verify_project_access(project_id, current_user, db)
    result = await db.execute(
        select(IndexingJob)
        .where(IndexingJob.project_id == project_id)
        .order_by(IndexingJob.started_at.desc().nulls_last())
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No indexing jobs found",
        )
    return IndexingJobResponse.model_validate(job)


@router.get("/projects/{project_id}/knowledge/stats")
async def get_knowledge_stats(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    graph: KnowledgeGraphManager = Depends(get_graph),
):
    """Get knowledge graph statistics for a project."""
    await _verify_project_access(project_id, current_user, db)
    stats = await graph.get_project_stats(str(project_id))
    return stats
