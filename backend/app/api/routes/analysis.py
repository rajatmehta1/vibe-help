"""Analysis API — realtime code analysis against active policies."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.policies.engine import evaluate_code
from app.db.session import get_db
from app.models.database import Policy, Project, User, user_organizations

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
