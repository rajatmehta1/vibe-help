"""Audit log API — query audit trail for a project."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.database import AuditLog, Project, User, user_organizations
from app.models.schemas import AuditLogResponse

router = APIRouter(tags=["audit"])


async def _verify_project_access(
    project_id: uuid.UUID, user: User, db: AsyncSession
) -> Project:
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


@router.get(
    "/projects/{project_id}/audit",
    response_model=list[AuditLogResponse],
)
async def list_audit_logs(
    project_id: uuid.UUID,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLogResponse]:
    """List audit log entries for a project, newest first."""
    await _verify_project_access(project_id, current_user, db)

    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.project_id == project_id)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    logs = result.scalars().all()
    return [AuditLogResponse.model_validate(log) for log in logs]
