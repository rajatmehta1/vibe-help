"""Celery tasks for code indexing."""

from __future__ import annotations

import asyncio
import logging

from app.workers.celery_app import celery_app

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
