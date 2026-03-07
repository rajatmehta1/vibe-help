"""Celery tasks for code indexing and project scanning."""

from __future__ import annotations

import asyncio
import logging
import os

from app.workers.celery_app import celery_app

# ---------------------------------------------------------------------------
# File-walking helpers for project scanning
# ---------------------------------------------------------------------------

_EXT_LANG: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".java": "java",
    ".cs": "csharp",
    ".rs": "rust",
}

_SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", ".next",
    "dist", "build", "coverage", ".pytest_cache", "migrations",
    ".mypy_cache", ".ruff_cache", ".tox", "htmlcov",
}

_MAX_FILE_BYTES = 512 * 1024  # 512 KB — skip very large files


def _iter_code_files(root: str):
    """Yield (abs_path, language) for every scannable code file under root."""
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs in-place so os.walk doesn't descend into them
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            lang = _EXT_LANG.get(ext)
            if lang:
                yield os.path.join(dirpath, fname), lang

logger = logging.getLogger("forgeline.tasks")


def _run_async(coro):
    """Run an async coroutine in a new event loop (Celery workers are synchronous)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="forgeline.run_indexing_job", bind=True, max_retries=1)
def run_indexing_job(self, project_id: str, root_path: str, job_id: str, job_type: str):
    """Execute a full or incremental indexing job.

    Creates its own async DB session and graph manager since Celery
    workers are synchronous processes.
    """
    logger.info(
        "Starting %s indexing job %s for project %s (path: %s)",
        job_type,
        job_id,
        project_id,
        root_path,
    )

    async def _do_index():
        from app.core.indexer.orchestrator import IndexingOrchestrator
        from app.core.knowledge.graph_manager import KnowledgeGraphManager
        from app.db.session import async_session

        graph = KnowledgeGraphManager()
        try:
            async with async_session() as db:
                orchestrator = IndexingOrchestrator(db=db, graph=graph)
                if job_type == "incremental":
                    await orchestrator.run_incremental_index(
                        project_id, root_path, job_id
                    )
                else:
                    await orchestrator.run_full_index(
                        project_id, root_path, job_id
                    )
        finally:
            await graph.close()

    try:
        _run_async(_do_index())
    except Exception as exc:
        logger.exception("Indexing task failed: %s", exc)

        # Mark job as FAILED in the database
        async def _mark_failed():
            from datetime import datetime, timezone

            from sqlalchemy import update as sql_update

            from app.db.session import async_session
            from app.models.database import IndexingJob
            from app.models.enums import ScanStatus

            async with async_session() as db:
                await db.execute(
                    sql_update(IndexingJob)
                    .where(IndexingJob.id == job_id)
                    .values(
                        status=ScanStatus.FAILED,
                        error_message=str(exc)[:2000],
                        completed_at=datetime.now(timezone.utc),
                    )
                )
                await db.commit()

        _run_async(_mark_failed())
        raise


@celery_app.task(name="forgeline.run_convention_learning", bind=True, max_retries=1)
def run_convention_learning(self, project_id: str):
    """Run convention learning for a project after indexing.

    Detects patterns, naming conventions, architecture layers, etc.
    """
    logger.info("Starting convention learning for project %s", project_id)

    async def _do_learn():
        from app.core.knowledge.convention_learner import ConventionLearner
        from app.core.knowledge.graph_manager import KnowledgeGraphManager
        from app.db.session import async_session

        graph = KnowledgeGraphManager()
        try:
            async with async_session() as db:
                learner = ConventionLearner(graph=graph, db=db)
                result = await learner.learn_all_conventions(project_id)
                logger.info(
                    "Convention learning complete for %s: %d patterns",
                    project_id,
                    result["patterns_count"],
                )
                return result
        finally:
            await graph.close()

    try:
        return _run_async(_do_learn())
    except Exception as exc:
        logger.exception("Convention learning failed: %s", exc)
        raise


@celery_app.task(name="forgeline.run_project_scan", bind=True, max_retries=1)
def run_project_scan(self, project_id: str, scan_id: str, root_path: str):
    """Walk the project root_path, run policy checks on every code file,
    and persist Scan + Violation records to PostgreSQL.
    """
    logger.info("Starting project scan %s for project %s (path: %s)", scan_id, project_id, root_path)

    async def _do_scan():
        from datetime import datetime, timezone
        from sqlalchemy import select, update as sql_update
        from app.core.policies.engine import evaluate_code
        from app.db.session import async_session
        from app.models.database import Policy, Scan, Violation
        from app.models.enums import ScanStatus

        # Step 1: mark RUNNING — own session, closed before heavy work
        async with async_session() as db:
            await db.execute(
                sql_update(Scan).where(Scan.id == scan_id).values(
                    status=ScanStatus.RUNNING,
                    started_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()

        # Step 2: fetch policies — own session, extract plain data before closing
        policy_dicts = []
        category_policy_ids: dict[str, object] = {}   # category → policy_id (UUID)
        category_severity: dict[str, object] = {}      # category → SeverityLevel

        async with async_session() as db:
            result = await db.execute(
                select(Policy).where(
                    Policy.project_id == project_id,
                    Policy.is_active == True,  # noqa: E712
                )
            )
            policies = result.scalars().all()
            for p in policies:
                cat = p.category.value
                policy_dicts.append({
                    "category": cat,
                    "severity_default": p.severity_default.value,
                    "is_active": True,
                    "configuration": p.configuration,
                })
                if cat not in category_policy_ids:
                    category_policy_ids[cat] = p.id
                    category_severity[cat] = p.severity_default

        if not policy_dicts:
            logger.warning("No active policies for project %s — scan will find no violations", project_id)

        # Step 3: walk files and run analysis — pure CPU/IO, no DB
        pending_violations: list[dict] = []
        files_scanned = 0

        for abs_path, language in _iter_code_files(root_path):
            try:
                if os.path.getsize(abs_path) > _MAX_FILE_BYTES:
                    logger.debug("Skipping large file %s", abs_path)
                    continue
                with open(abs_path, encoding="utf-8", errors="ignore") as fh:
                    code = fh.read()
            except OSError:
                continue

            rel_path = os.path.relpath(abs_path, root_path).replace("\\", "/")
            analysis = evaluate_code(
                code=code,
                file_path=rel_path,
                language=language,
                policies=policy_dicts,
            )
            files_scanned += 1

            for v in analysis.violations:
                policy_id = category_policy_ids.get(v.category)
                severity = category_severity.get(v.category)
                if policy_id is None:
                    continue
                pending_violations.append({
                    "scan_id": scan_id,
                    "policy_id": policy_id,
                    "severity": severity,
                    "file_path": rel_path,
                    "line_start": v.line_start,
                    "line_end": v.line_end,
                    "column_start": v.column_start,
                    "column_end": v.column_end,
                    "message": v.message,
                    "suggestion": v.suggestion,
                    "code_snippet": v.code_snippet,
                    "context_evidence": v.context_evidence,
                })

        # Step 4: persist violations + mark COMPLETED — own session
        total_violations = len(pending_violations)
        async with async_session() as db:
            for vd in pending_violations:
                db.add(Violation(**vd))
            await db.flush()
            await db.execute(
                sql_update(Scan).where(Scan.id == scan_id).values(
                    status=ScanStatus.COMPLETED,
                    total_violations=total_violations,
                    completed_at=datetime.now(timezone.utc),
                    metadata_={"files_scanned": files_scanned},
                )
            )
            await db.commit()

        logger.info("Scan %s complete: %d files, %d violations", scan_id, files_scanned, total_violations)
        return {"files_scanned": files_scanned, "total_violations": total_violations}

    try:
        return _run_async(_do_scan())
    except Exception as exc:
        logger.exception("Project scan failed: %s", exc)
        # Mark failed in its own isolated run to avoid sharing broken connections
        async def _mark_failed():
            from datetime import datetime, timezone
            from sqlalchemy import update as sql_update
            from app.db.session import async_session
            from app.models.database import Scan
            from app.models.enums import ScanStatus
            async with async_session() as db:
                await db.execute(
                    sql_update(Scan).where(Scan.id == scan_id).values(
                        status=ScanStatus.FAILED,
                        completed_at=datetime.now(timezone.utc),
                        metadata_={"error": str(exc)[:2000]},
                    )
                )
                await db.commit()

        try:
            _run_async(_mark_failed())
        except Exception:
            logger.exception("Failed to mark scan %s as failed", scan_id)
        raise
