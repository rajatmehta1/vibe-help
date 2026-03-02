import uuid

import yaml
from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.database import Policy, PolicyTemplate, Project, User, Violation, user_organizations
from app.models.enums import PolicyCategory, SeverityLevel
from app.models.schemas import PolicyResponse, PolicyTemplateResponse, PolicyUpdate

router = APIRouter(tags=["policies"])


# ---- request models ----


class PolicyCreateRequest(BaseModel):
    policy_template_id: uuid.UUID | None = None
    name: str
    description: str | None = None
    category: PolicyCategory
    severity_default: SeverityLevel
    is_active: bool = True
    configuration: dict | None = None


# ---- response models ----


class PolicyDetailResponse(PolicyResponse):
    violation_count: int = 0


# ---- helpers ----


async def _verify_project_access(
    project_id: uuid.UUID, user: User, db: AsyncSession
) -> Project:
    result = await db.execute(
        select(user_organizations.c.org_id).where(user_organizations.c.user_id == user.id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User has no organization")

    proj_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.org_id == row.org_id)
    )
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


async def _get_policy_or_404(
    policy_id: uuid.UUID, project_id: uuid.UUID, db: AsyncSession
) -> Policy:
    result = await db.execute(
        select(Policy).where(Policy.id == policy_id, Policy.project_id == project_id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    return policy


# ---- builtin templates (no auth) ----


@router.get("/policies/builtin", response_model=list[PolicyTemplateResponse])
async def list_builtin_templates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PolicyTemplate)
        .where(PolicyTemplate.is_builtin == True)  # noqa: E712
        .order_by(PolicyTemplate.category)
    )
    return [PolicyTemplateResponse.model_validate(t) for t in result.scalars().all()]


# ---- project-scoped policy endpoints ----


@router.post(
    "/projects/{project_id}/policies",
    response_model=PolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_policy(
    project_id: uuid.UUID,
    body: PolicyCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project_access(project_id, current_user, db)

    config = body.configuration
    category = body.category
    severity = body.severity_default
    name = body.name
    description = body.description

    if body.policy_template_id:
        tmpl_result = await db.execute(
            select(PolicyTemplate).where(PolicyTemplate.id == body.policy_template_id)
        )
        template = tmpl_result.scalar_one_or_none()
        if not template:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
        if config is None:
            config = template.default_configuration
        if not name:
            name = template.name
        if not description:
            description = template.description
        category = template.category
        severity = template.default_severity

    policy = Policy(
        id=uuid.uuid4(),
        project_id=project_id,
        policy_template_id=body.policy_template_id,
        name=name,
        description=description,
        category=category,
        severity_default=severity,
        is_active=body.is_active,
        configuration=config,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return PolicyResponse.model_validate(policy)


@router.get("/projects/{project_id}/policies", response_model=list[PolicyResponse])
async def list_policies(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project_access(project_id, current_user, db)
    result = await db.execute(
        select(Policy)
        .where(Policy.project_id == project_id)
        .order_by(Policy.category, Policy.name)
    )
    return [PolicyResponse.model_validate(p) for p in result.scalars().all()]


@router.get(
    "/projects/{project_id}/policies/{policy_id}",
    response_model=PolicyDetailResponse,
)
async def get_policy(
    project_id: uuid.UUID,
    policy_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project_access(project_id, current_user, db)
    policy = await _get_policy_or_404(policy_id, project_id, db)

    count_result = await db.execute(
        select(func.count()).select_from(Violation).where(Violation.policy_id == policy_id)
    )
    violation_count = count_result.scalar() or 0

    resp = PolicyDetailResponse.model_validate(policy)
    resp.violation_count = violation_count
    return resp


@router.put(
    "/projects/{project_id}/policies/{policy_id}",
    response_model=PolicyResponse,
)
async def update_policy(
    project_id: uuid.UUID,
    policy_id: uuid.UUID,
    body: PolicyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project_access(project_id, current_user, db)
    policy = await _get_policy_or_404(policy_id, project_id, db)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(policy, field, value)

    await db.commit()
    await db.refresh(policy)
    return PolicyResponse.model_validate(policy)


@router.delete(
    "/projects/{project_id}/policies/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_policy(
    project_id: uuid.UUID,
    policy_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project_access(project_id, current_user, db)
    await _get_policy_or_404(policy_id, project_id, db)
    await db.execute(delete(Policy).where(Policy.id == policy_id))
    await db.commit()


@router.post(
    "/projects/{project_id}/policies/import",
    response_model=PolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_policy_yaml(
    project_id: uuid.UUID,
    yaml_body: str = Body(..., media_type="text/plain"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project_access(project_id, current_user, db)

    try:
        parsed = yaml.safe_load(yaml_body)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid YAML: {e}")

    if not isinstance(parsed, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="YAML must be a mapping")

    required = {"name", "category", "severity_default"}
    missing = required - parsed.keys()
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required fields: {', '.join(missing)}",
        )

    try:
        category = PolicyCategory(parsed["category"])
        severity = SeverityLevel(parsed["severity_default"])
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    policy = Policy(
        id=uuid.uuid4(),
        project_id=project_id,
        name=parsed["name"],
        description=parsed.get("description"),
        category=category,
        severity_default=severity,
        is_active=parsed.get("is_active", True),
        configuration=parsed.get("configuration"),
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return PolicyResponse.model_validate(policy)
