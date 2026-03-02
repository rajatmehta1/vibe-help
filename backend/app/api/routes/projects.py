import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.database import Policy, Project, Scan, User, user_organizations
from app.models.schemas import ProjectResponse, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


# ---- request models ----


class ProjectCreateRequest(BaseModel):
    name: str
    description: str | None = None
    root_path: str | None = None
    primary_language: str | None = None
    settings: dict | None = None


# ---- response models ----


class ProjectDetailResponse(ProjectResponse):
    policy_count: int = 0
    last_scan_at: str | None = None
    last_indexed_at_str: str | None = None


# ---- helpers ----


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return re.sub(r"-+", "-", slug).strip("-")


async def _get_user_org_id(user: User, db: AsyncSession) -> uuid.UUID:
    result = await db.execute(
        select(user_organizations.c.org_id).where(user_organizations.c.user_id == user.id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User has no organization")
    return row.org_id


async def _get_project_or_404(
    project_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession
) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.org_id == org_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


# ---- endpoints ----


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_id = await _get_user_org_id(current_user, db)
    project = Project(
        id=uuid.uuid4(),
        org_id=org_id,
        name=body.name,
        slug=_slugify(body.name),
        description=body.description,
        root_path=body.root_path,
        primary_language=body.primary_language,
        settings=body.settings,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_id = await _get_user_org_id(current_user, db)
    result = await db.execute(
        select(Project).where(Project.org_id == org_id).order_by(Project.created_at.desc())
    )
    return [ProjectResponse.model_validate(p) for p in result.scalars().all()]


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_id = await _get_user_org_id(current_user, db)
    project = await _get_project_or_404(project_id, org_id, db)

    policy_count_result = await db.execute(
        select(func.count()).select_from(Policy).where(Policy.project_id == project_id)
    )
    policy_count = policy_count_result.scalar() or 0

    last_scan_result = await db.execute(
        select(Scan.completed_at)
        .where(Scan.project_id == project_id)
        .order_by(Scan.completed_at.desc().nulls_last())
        .limit(1)
    )
    last_scan_row = last_scan_result.first()
    last_scan_at = last_scan_row[0].isoformat() if last_scan_row and last_scan_row[0] else None

    resp = ProjectDetailResponse.model_validate(project)
    resp.policy_count = policy_count
    resp.last_scan_at = last_scan_at
    return resp


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_id = await _get_user_org_id(current_user, db)
    project = await _get_project_or_404(project_id, org_id, db)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_id = await _get_user_org_id(current_user, db)
    await _get_project_or_404(project_id, org_id, db)
    await db.execute(delete(Project).where(Project.id == project_id))
    await db.commit()
