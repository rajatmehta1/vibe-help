"""Knowledge API endpoints — patterns, conventions, architecture, similarity."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_graph
from app.core.knowledge.graph_manager import KnowledgeGraphManager
from app.db.session import get_db
from app.models.database import AuditLog, Project, User, user_organizations
from app.models.enums import AuditAction

router = APIRouter(tags=["knowledge"])


# ---- request / response models ----


class SimilarCodeRequest(BaseModel):
    code: str
    language: str
    limit: int = 5


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


# ---- endpoints ----


@router.get("/projects/{project_id}/patterns")
async def list_patterns(
    project_id: uuid.UUID,
    type: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    graph: KnowledgeGraphManager = Depends(get_graph),
):
    """List all detected patterns for a project, optionally filtered by type."""
    await _verify_project_access(project_id, current_user, db)
    patterns = await graph.get_patterns(str(project_id))
    if type:
        patterns = [p for p in patterns if p.get("category") == type]
    return {"patterns": patterns, "count": len(patterns)}


@router.get("/projects/{project_id}/patterns/{pattern_id}/evidence")
async def get_pattern_evidence(
    project_id: uuid.UUID,
    pattern_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    graph: KnowledgeGraphManager = Depends(get_graph),
):
    """Get concrete code examples that follow a specific pattern."""
    await _verify_project_access(project_id, current_user, db)

    from app.core.knowledge.convention_learner import ConventionLearner

    learner = ConventionLearner(graph=graph, db=db)
    evidence = await learner.get_pattern_evidence(str(project_id), pattern_id)
    return {"pattern_id": pattern_id, "evidence": evidence, "count": len(evidence)}


@router.get("/projects/{project_id}/conventions")
async def list_conventions(
    project_id: uuid.UUID,
    category: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    graph: KnowledgeGraphManager = Depends(get_graph),
):
    """List all conventions for a project, optionally filtered by category."""
    await _verify_project_access(project_id, current_user, db)
    conventions = await graph.get_conventions(str(project_id))
    if category:
        conventions = [c for c in conventions if c.get("category") == category]
    return {"conventions": conventions, "count": len(conventions)}


@router.get("/projects/{project_id}/architecture")
async def get_architecture(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    graph: KnowledgeGraphManager = Depends(get_graph),
):
    """Get architectural overview — layers and cross-layer relationships."""
    await _verify_project_access(project_id, current_user, db)
    overview = await graph.get_architectural_overview(str(project_id))
    return overview


@router.post("/projects/{project_id}/similar")
async def find_similar_code(
    project_id: uuid.UUID,
    body: SimilarCodeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    graph: KnowledgeGraphManager = Depends(get_graph),
):
    """Find code units similar to the provided code snippet."""
    await _verify_project_access(project_id, current_user, db)

    from app.core.indexer.embedding_builder import EmbeddingBuilder
    from app.core.knowledge.similarity import SimilaritySearch

    embeddings = EmbeddingBuilder(db)
    search = SimilaritySearch(graph=graph, embedding_builder=embeddings, db=db)
    results = await search.find_similar_code(
        project_id=str(project_id),
        code_text=body.code,
        language=body.language,
        limit=body.limit,
    )
    return {"results": results, "count": len(results)}


@router.post(
    "/projects/{project_id}/learn",
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_convention_learning(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger convention learning for a project via Celery background task."""
    project = await _verify_project_access(project_id, current_user, db)

    audit = AuditLog(
        id=uuid.uuid4(),
        project_id=project.id,
        user_id=current_user.id,
        action=AuditAction.INDEX_STARTED,
        details={"task": "convention_learning"},
    )
    db.add(audit)
    await db.commit()

    from app.workers.indexing_tasks import run_convention_learning

    run_convention_learning.delay(project_id=str(project_id))

    return {"status": "accepted", "message": "Convention learning started"}
