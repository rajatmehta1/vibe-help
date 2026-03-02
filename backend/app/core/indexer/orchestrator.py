"""Orchestrates full and incremental code indexing."""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.indexer.embedding_builder import (
    EmbeddingBuilder,
    _content_hash,
    _format_input,
)
from app.core.indexer.graph_builder import GraphBuilder, _make_file_id
from app.core.indexer.parsers import ParserRegistry
from app.core.indexer.parsers.base import ParsedFile
from app.core.knowledge.graph_manager import KnowledgeGraphManager
from app.models.database import CodeEmbedding, IndexingJob, Project
from app.models.enums import CodeUnitType, ScanStatus

logger = logging.getLogger("forgeline.orchestrator")

# Directories to skip during indexing
SKIP_DIRS = frozenset({
    "node_modules", "__pycache__", ".git", ".venv", "venv",
    "dist", "build", ".next", "coverage", ".tox", ".mypy_cache",
    ".pytest_cache", "egg-info", ".eggs", ".svn", ".hg",
})

# File suffixes to skip
SKIP_SUFFIXES = frozenset({
    ".min.js", ".min.css", ".map", ".lock",
    ".pyc", ".pyo", ".so", ".dylib", ".dll",
    ".woff", ".woff2", ".ttf", ".eot",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
    ".pdf", ".zip", ".tar", ".gz",
})

# Dependency manifest filenames
DEPENDENCY_FILES = frozenset({
    "package.json", "requirements.txt", "pyproject.toml",
})


def _should_skip_dir(dir_name: str) -> bool:
    return dir_name in SKIP_DIRS or dir_name.startswith(".")


def _should_skip_file(file_name: str) -> bool:
    lower = file_name.lower()
    return any(lower.endswith(suffix) for suffix in SKIP_SUFFIXES)


def _file_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _map_unit_type(parser_type: str) -> CodeUnitType:
    """Map parser unit type string to the CodeUnitType enum for PG."""
    mapping = {
        "function": CodeUnitType.FUNCTION,
        "class": CodeUnitType.CLASS,
        "interface": CodeUnitType.MODULE,
        "variable": CodeUnitType.MODULE,
        "module": CodeUnitType.MODULE,
    }
    return mapping.get(parser_type, CodeUnitType.FILE)


class IndexingOrchestrator:
    """Coordinates indexing: walk files, parse, build graph, generate embeddings."""

    def __init__(
        self,
        db: AsyncSession,
        graph: KnowledgeGraphManager,
    ) -> None:
        self._db = db
        self._graph = graph
        self._graph_builder = GraphBuilder(graph)
        self._embedding_builder = EmbeddingBuilder()
        self._parser_registry = ParserRegistry()

    async def run_full_index(
        self, project_id: str, root_path: str, job_id: str
    ) -> None:
        """Full indexing: walk the entire directory tree."""
        await self._update_job(
            job_id, status=ScanStatus.RUNNING, started_at=datetime.now(timezone.utc)
        )

        try:
            # Phase 1: Discover files
            source_files, dep_files = self._discover_files(root_path)
            total = len(source_files) + len(dep_files)
            await self._update_job(job_id, total_files=total)

            all_parsed: list[ParsedFile] = []
            processed = 0

            # Phase 2: Parse + graph + embed each source file
            for rel_path, full_path in source_files:
                try:
                    content = self._read_file(full_path)
                    if content is None:
                        processed += 1
                        continue

                    parsed = self._parse_file(rel_path, content)
                    if parsed:
                        await self._graph_builder.index_file(project_id, parsed)
                        await self._embed_parsed_file(project_id, parsed, content)
                        all_parsed.append(parsed)
                except Exception:
                    logger.exception("Error indexing file %s", rel_path)

                processed += 1
                if processed % 50 == 0:
                    await self._update_job(job_id, processed_files=processed)
                    await self._db.commit()

            # Phase 3: Index dependency files
            for rel_path, full_path in dep_files:
                try:
                    content = self._read_file(full_path)
                    if content:
                        await self._graph_builder.index_dependencies(
                            project_id, rel_path, content
                        )
                except Exception:
                    logger.exception("Error indexing dependency file %s", rel_path)
                processed += 1

            # Phase 4: Build call graph (second pass)
            if all_parsed:
                await self._graph_builder.build_call_graph(project_id, all_parsed)

            # Phase 5: Finalize
            await self._db.execute(
                update(Project)
                .where(Project.id == project_id)
                .values(last_indexed_at=datetime.now(timezone.utc))
            )

            await self._update_job(
                job_id,
                status=ScanStatus.COMPLETED,
                processed_files=total,
                completed_at=datetime.now(timezone.utc),
            )
            await self._db.commit()
            logger.info(
                "Full index complete: %d files processed for project %s",
                total,
                project_id,
            )

        except Exception as e:
            logger.exception("Full index failed for project %s", project_id)
            await self._update_job(
                job_id,
                status=ScanStatus.FAILED,
                error_message=str(e)[:2000],
                completed_at=datetime.now(timezone.utc),
            )
            await self._db.commit()

    async def run_incremental_index(
        self, project_id: str, root_path: str, job_id: str
    ) -> None:
        """Incremental indexing: only process changed/new files, remove deleted ones."""
        await self._update_job(
            job_id, status=ScanStatus.RUNNING, started_at=datetime.now(timezone.utc)
        )

        try:
            # Build hash map of existing embeddings: file_path -> {unit_name: content_hash}
            existing = await self._db.execute(
                select(
                    CodeEmbedding.file_path,
                    CodeEmbedding.code_unit_name,
                    CodeEmbedding.content_hash,
                ).where(CodeEmbedding.project_id == project_id)
            )
            existing_hashes: dict[str, dict[str, str]] = {}
            for row in existing.fetchall():
                existing_hashes.setdefault(row.file_path, {})[
                    row.code_unit_name
                ] = row.content_hash
            known_paths = set(existing_hashes.keys())

            # Discover current files on disk
            source_files, dep_files = self._discover_files(root_path)
            current_paths = {rel for rel, _ in source_files}

            # Detect removed files
            removed_paths = known_paths - current_paths
            for removed_path in removed_paths:
                file_id = _make_file_id(project_id, removed_path)
                await self._graph.delete_file_subgraph(file_id)
                await self._embedding_builder.delete_file_embeddings(
                    self._db, project_id, removed_path
                )

            # Find changed/new files
            files_to_process: list[tuple[str, str, str]] = []
            for rel_path, full_path in source_files:
                content = self._read_file(full_path)
                if content is None:
                    continue
                file_hash = _file_hash(content)
                old_units = existing_hashes.get(rel_path, {})
                old_file_hash = old_units.get("__file__", "")
                if file_hash != old_file_hash:
                    files_to_process.append((rel_path, full_path, content))

            total = len(files_to_process) + len(removed_paths) + len(dep_files)
            await self._update_job(job_id, total_files=total)

            all_parsed: list[ParsedFile] = []
            processed = len(removed_paths)

            for rel_path, full_path, content in files_to_process:
                try:
                    parsed = self._parse_file(rel_path, content)
                    if parsed:
                        await self._graph_builder.index_file(project_id, parsed)
                        await self._embed_parsed_file(project_id, parsed, content)
                        all_parsed.append(parsed)
                except Exception:
                    logger.exception("Error indexing file %s", rel_path)

                processed += 1
                if processed % 50 == 0:
                    await self._update_job(job_id, processed_files=processed)
                    await self._db.commit()

            # Dependency files
            for rel_path, full_path in dep_files:
                try:
                    content = self._read_file(full_path)
                    if content:
                        await self._graph_builder.index_dependencies(
                            project_id, rel_path, content
                        )
                except Exception:
                    logger.exception("Error indexing dependency file %s", rel_path)
                processed += 1

            # Call graph
            if all_parsed:
                await self._graph_builder.build_call_graph(project_id, all_parsed)

            await self._db.execute(
                update(Project)
                .where(Project.id == project_id)
                .values(last_indexed_at=datetime.now(timezone.utc))
            )

            await self._update_job(
                job_id,
                status=ScanStatus.COMPLETED,
                processed_files=processed,
                completed_at=datetime.now(timezone.utc),
            )
            await self._db.commit()
            logger.info(
                "Incremental index complete: %d changed, %d removed for project %s",
                len(files_to_process),
                len(removed_paths),
                project_id,
            )

        except Exception as e:
            logger.exception("Incremental index failed for project %s", project_id)
            await self._update_job(
                job_id,
                status=ScanStatus.FAILED,
                error_message=str(e)[:2000],
                completed_at=datetime.now(timezone.utc),
            )
            await self._db.commit()

    # ---- Internal helpers ----

    def _discover_files(
        self, root_path: str
    ) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        """Walk directory tree, return (source_files, dependency_files).

        Each item is (relative_path, absolute_path).
        """
        source_files: list[tuple[str, str]] = []
        dep_files: list[tuple[str, str]] = []
        supported = set(self._parser_registry.supported_extensions())
        root = Path(root_path)

        for dirpath, dirnames, filenames in os.walk(root):
            # Filter skip directories in-place
            dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]

            for filename in filenames:
                if _should_skip_file(filename):
                    continue

                full_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(full_path, root).replace("\\", "/")

                if filename in DEPENDENCY_FILES:
                    dep_files.append((rel_path, full_path))
                    continue

                ext = ""
                if "." in filename:
                    ext = "." + filename.rsplit(".", 1)[-1]
                if ext in supported:
                    source_files.append((rel_path, full_path))

        return source_files, dep_files

    def _read_file(self, full_path: str) -> str | None:
        """Read file content, return None if unreadable or too large."""
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if len(content) > 1_000_000:
                logger.warning(
                    "Skipping large file: %s (%d bytes)", full_path, len(content)
                )
                return None
            return content
        except (OSError, IOError) as e:
            logger.warning("Cannot read file %s: %s", full_path, e)
            return None

    def _parse_file(self, rel_path: str, content: str) -> ParsedFile | None:
        """Parse a file using the appropriate parser."""
        parser = self._parser_registry.get_parser(rel_path)
        if parser is None:
            return None
        try:
            return parser.parse(rel_path, content)
        except Exception:
            logger.exception("Parser error for %s", rel_path)
            return None

    async def _embed_parsed_file(
        self, project_id: str, parsed: ParsedFile, raw_content: str
    ) -> None:
        """Generate and store embeddings for all code units in a parsed file."""
        file_hash = _file_hash(raw_content)

        # File-level embedding (truncated content for embedding, full hash for comparison)
        file_text = _format_input(
            parsed.language,
            "file",
            parsed.path.rsplit("/", 1)[-1],
            parsed.path,
            raw_content[:3000],
        )
        file_embedding = self._embedding_builder.generate_embedding(file_text)
        await self._embedding_builder.store_embedding(
            self._db,
            project_id,
            parsed.path,
            CodeUnitType.FILE,
            "__file__",
            file_hash,
            file_embedding,
            metadata={
                "language": parsed.language,
                "lines_of_code": parsed.lines_of_code,
            },
        )

        # Collect code units to embed
        units_to_embed: list[tuple[ParsedFile, str, str]] = []
        for unit in parsed.code_units:
            text = _format_input(
                parsed.language,
                unit.type,
                unit.name,
                parsed.path,
                unit.body_text[:3000],
            )
            units_to_embed.append((unit, text, _content_hash(unit.body_text)))
            # Class methods
            for child in unit.children:
                child_text = _format_input(
                    parsed.language,
                    child.type,
                    f"{unit.name}.{child.name}",
                    parsed.path,
                    child.body_text[:3000],
                )
                units_to_embed.append(
                    (child, child_text, _content_hash(child.body_text))
                )

        if not units_to_embed:
            return

        # Batch generate embeddings
        texts = [t for _, t, _ in units_to_embed]
        embeddings = self._embedding_builder.batch_generate(texts)

        # Store each embedding
        for (unit, _, chash), emb in zip(units_to_embed, embeddings):
            await self._embedding_builder.store_embedding(
                self._db,
                project_id,
                parsed.path,
                _map_unit_type(unit.type),
                unit.name,
                chash,
                emb,
                metadata={
                    "language": parsed.language,
                    "line_start": unit.line_start,
                    "line_end": unit.line_end,
                    "is_async": unit.is_async,
                    "complexity": unit.complexity,
                },
            )

    async def _update_job(self, job_id: str, **kwargs: Any) -> None:
        """Update IndexingJob fields."""
        if kwargs:
            await self._db.execute(
                update(IndexingJob).where(IndexingJob.id == job_id).values(**kwargs)
            )
