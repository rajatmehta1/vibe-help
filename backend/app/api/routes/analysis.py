"""Analysis API — realtime code analysis against active policies."""

from __future__ import annotations

import uuid

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.policies.engine import evaluate_code
from app.db.session import get_db
from app.models.database import AuditLog, Policy, Project, Scan, User, Violation, user_organizations
from app.models.enums import ScanStatus, ScanType

router = APIRouter(tags=["analysis"])


# ---- request / response models ----


class AnalyzeRequest(BaseModel):
    code: str
    file_path: str = "untitled"
    language: str = "python"


class ViolationItem(BaseModel):
    rule_id: str
    policy_name: str
    category: str
    severity: str
    message: str
    suggestion: str | None = None
    line_start: int = 1
    line_end: int = 1
    column_start: int = 1
    column_end: int = 1
    code_snippet: str | None = None


class AnalyzeResponse(BaseModel):
    violations: list[ViolationItem]
    violation_count: int
    elapsed_ms: float
    cached: bool = False


# ---- helpers ----


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


# ---- endpoints ----


@router.post(
    "/projects/{project_id}/analyze",
    response_model=AnalyzeResponse,
)
async def analyze_code(
    project_id: uuid.UUID,
    body: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalyzeResponse:
    """Analyze a code snippet against the project's active policies.

    This is the realtime endpoint used by the VS Code extension.
    Rule-based checks run synchronously; results are cached for 5 minutes.
    """
    await _verify_project_access(project_id, current_user, db)

    # Fetch active policies for this project
    result = await db.execute(
        select(Policy).where(
            Policy.project_id == project_id,
            Policy.is_active == True,  # noqa: E712
        )
    )
    policies_rows = result.scalars().all()

    policy_dicts = [
        {
            "category": p.category.value if hasattr(p.category, "value") else str(p.category),
            "severity_default": p.severity_default.value if hasattr(p.severity_default, "value") else str(p.severity_default),
            "is_active": p.is_active,
            "configuration": p.configuration,
        }
        for p in policies_rows
    ]

    # Run the evaluation engine
    analysis = evaluate_code(
        code=body.code,
        file_path=body.file_path,
        language=body.language,
        policies=policy_dicts,
    )

    violations = [
        ViolationItem(
            rule_id=v.rule_id,
            policy_name=v.policy_name,
            category=v.category,
            severity=v.severity,
            message=v.message,
            suggestion=v.suggestion,
            line_start=v.line_start,
            line_end=v.line_end,
            column_start=v.column_start,
            column_end=v.column_end,
            code_snippet=v.code_snippet,
        )
        for v in analysis.violations
    ]

    return AnalyzeResponse(
        violations=violations,
        violation_count=len(violations),
        elapsed_ms=analysis.elapsed_ms,
        cached=analysis.cached,
    )


@router.post("/projects/{project_id}/scan", status_code=status.HTTP_202_ACCEPTED)
async def trigger_project_scan(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a full workspace scan — walks root_path, checks every code file
    against active policies, and stores violations in PostgreSQL."""
    project = await _verify_project_access(project_id, current_user, db)
    if not project.root_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no root_path configured. Set it in Settings first.",
        )

    scan = Scan(
        id=uuid.uuid4(),
        project_id=project.id,
        scan_type=ScanType.WORKSPACE,
        status=ScanStatus.PENDING,
        trigger_source="dashboard",
        started_at=datetime.now(timezone.utc),
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    from app.workers.indexing_tasks import run_project_scan
    run_project_scan.delay(
        project_id=str(project_id),
        scan_id=str(scan.id),
        root_path=project.root_path,
    )

    return {
        "scan_id": str(scan.id),
        "status": "accepted",
        "message": "Project scan started",
    }


@router.get("/projects/{project_id}/scan/status")
async def get_scan_status(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the most recent workspace scan status for a project."""
    await _verify_project_access(project_id, current_user, db)
    result = await db.execute(
        select(Scan)
        .where(Scan.project_id == project_id, Scan.scan_type == ScanType.WORKSPACE)
        .order_by(Scan.started_at.desc().nulls_last())
        .limit(1)
    )
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No scans found")
    return {
        "id": str(scan.id),
        "status": scan.status.value,
        "total_violations": scan.total_violations,
        "started_at": scan.started_at.isoformat() if scan.started_at else None,
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        "metadata_": scan.metadata_,
    }


@router.get("/projects/{project_id}/scans/{scan_id}/violations")
async def list_scan_violations(
    project_id: uuid.UUID,
    scan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all violations for a specific scan."""
    await _verify_project_access(project_id, current_user, db)
    # Verify the scan belongs to this project
    scan_result = await db.execute(
        select(Scan).where(Scan.id == scan_id, Scan.project_id == project_id)
    )
    if not scan_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")

    result = await db.execute(
        select(Violation)
        .where(Violation.scan_id == scan_id)
        .order_by(Violation.file_path, Violation.line_start)
    )
    violations = result.scalars().all()
    return [
        {
            "id": str(v.id),
            "file_path": v.file_path,
            "line_start": v.line_start,
            "line_end": v.line_end,
            "column_start": v.column_start,
            "column_end": v.column_end,
            "severity": v.severity.value if hasattr(v.severity, "value") else v.severity,
            "message": v.message,
            "suggestion": v.suggestion,
            "code_snippet": v.code_snippet,
        }
        for v in violations
    ]


@router.get("/projects/{project_id}/stats")
async def get_project_stats(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate stats for the dashboard: total violations, over-time chart, top policies, recent activity."""
    await _verify_project_access(project_id, current_user, db)

    # Total violations across all scans for this project
    total_result = await db.execute(
        select(func.count(Violation.id))
        .join(Scan, Violation.scan_id == Scan.id)
        .where(Scan.project_id == project_id)
    )
    total_violations = total_result.scalar() or 0

    # Violations over time — last 20 completed scans ordered chronologically
    scans_result = await db.execute(
        select(Scan.started_at, Scan.total_violations)
        .where(
            Scan.project_id == project_id,
            Scan.status == ScanStatus.COMPLETED,
            Scan.total_violations > 0,
        )
        .order_by(Scan.started_at.asc())
        .limit(20)
    )
    scans_over_time = [
        {
            "date": row.started_at.strftime("%b %d") if row.started_at else "—",
            "total": row.total_violations,
        }
        for row in scans_result
    ]

    # Top violated policies (top 5 by violation count)
    top_result = await db.execute(
        select(Policy.name, func.count(Violation.id).label("violations"))
        .join(Violation, Violation.policy_id == Policy.id)
        .join(Scan, Violation.scan_id == Scan.id)
        .where(Scan.project_id == project_id)
        .group_by(Policy.id, Policy.name)
        .order_by(func.count(Violation.id).desc())
        .limit(5)
    )
    top_policies = [
        {"name": row.name, "violations": row.violations}
        for row in top_result
    ]

    # Recent audit log activity (last 10 entries)
    audit_result = await db.execute(
        select(AuditLog)
        .where(AuditLog.project_id == project_id)
        .order_by(AuditLog.created_at.desc())
        .limit(10)
    )
    audit_logs = [
        {
            "id": str(a.id),
            "project_id": str(a.project_id),
            "user_id": str(a.user_id) if a.user_id else None,
            "action": a.action,
            "details": a.details,
            "ip_address": a.ip_address,
            "created_at": a.created_at.isoformat(),
        }
        for a in audit_result.scalars().all()
    ]

    return {
        "total_violations": total_violations,
        "scans_over_time": scans_over_time,
        "top_policies": top_policies,
        "recent_activity": audit_logs,
    }


@router.get("/projects/{project_id}/scans")
async def list_scans(
    project_id: uuid.UUID,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List scan history for a project, most recent first."""
    await _verify_project_access(project_id, current_user, db)
    result = await db.execute(
        select(Scan)
        .where(Scan.project_id == project_id)
        .order_by(Scan.started_at.desc().nulls_last())
        .limit(limit)
    )
    scans = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "project_id": str(s.project_id),
            "scan_type": s.scan_type.value if hasattr(s.scan_type, "value") else s.scan_type,
            "status": s.status.value if hasattr(s.status, "value") else s.status,
            "file_path": s.file_path,
            "trigger_source": s.trigger_source,
            "total_violations": s.total_violations,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            "metadata_": s.metadata_,
        }
        for s in scans
    ]
