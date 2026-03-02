"""Embedding generation and vector storage for code indexing."""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import CodeEmbedding
from app.models.enums import CodeUnitType

logger = logging.getLogger("forgeline.embeddings")

EMBEDDING_DIM = 384


def _format_input(
    language: str, unit_type: str, name: str, file_path: str, code_text: str
) -> str:
    """Build the canonical embedding input string."""
    return (
        f"language: {language}\n"
        f"type: {unit_type}\n"
        f"name: {name}\n"
        f"context: {file_path}\n\n"
        f"{code_text}"
    )


def _content_hash(text: str) -> str:
    """SHA-256 of the input text, for change detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EmbeddingBuilder:
    """Generates embeddings via OpenAI or sentence-transformers, stores in pgvector."""

    def __init__(self) -> None:
        self._use_openai = bool(settings.OPENAI_API_KEY)
        self._model = None  # lazy init
        self._openai_client = None  # lazy init

    def _ensure_model(self) -> None:
        """Lazy-load the appropriate model on first call."""
        if self._use_openai:
            if self._openai_client is None:
                from openai import OpenAI

                self._openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info("Using OpenAI text-embedding-3-small (dim=%d)", EMBEDDING_DIM)
        else:
            if self._model is None:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("Using local all-MiniLM-L6-v2 (dim=%d)", EMBEDDING_DIM)

    def generate_embedding(self, text: str) -> list[float]:
        """Generate a single embedding vector."""
        self._ensure_model()
        if self._use_openai:
            response = self._openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
                dimensions=EMBEDDING_DIM,
            )
            return response.data[0].embedding
        else:
            vector = self._model.encode(text, normalize_embeddings=True)
            return vector.tolist()

    def batch_generate(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        if not texts:
            return []
        self._ensure_model()
        if self._use_openai:
            response = self._openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=texts,
                dimensions=EMBEDDING_DIM,
            )
            sorted_data = sorted(response.data, key=lambda x: x.index)
            return [item.embedding for item in sorted_data]
        else:
            vectors = self._model.encode(texts, normalize_embeddings=True)
            return [v.tolist() for v in vectors]

    async def store_embedding(
        self,
        db: AsyncSession,
        project_id: uuid.UUID | str,
        file_path: str,
        code_unit_type: CodeUnitType,
        code_unit_name: str,
        content_hash: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> CodeEmbedding:
        """Upsert a code embedding row keyed on (project_id, file_path, code_unit_name)."""
        pid = uuid.UUID(str(project_id)) if not isinstance(project_id, uuid.UUID) else project_id
        result = await db.execute(
            select(CodeEmbedding).where(
                CodeEmbedding.project_id == pid,
                CodeEmbedding.file_path == file_path,
                CodeEmbedding.code_unit_name == code_unit_name,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.content_hash = content_hash
            existing.embedding = embedding
            existing.code_unit_type = code_unit_type
            existing.metadata_ = metadata
        else:
            existing = CodeEmbedding(
                id=uuid.uuid4(),
                project_id=pid,
                file_path=file_path,
                code_unit_type=code_unit_type,
                code_unit_name=code_unit_name,
                content_hash=content_hash,
                embedding=embedding,
                metadata_=metadata,
            )
            db.add(existing)
        return existing

    async def find_similar(
        self,
        db: AsyncSession,
        project_id: uuid.UUID | str,
        query_embedding: list[float],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find code units similar to query_embedding using cosine distance."""
        pid = str(project_id)
        stmt = text("""
            SELECT id, file_path, code_unit_type, code_unit_name,
                   content_hash, metadata,
                   embedding <=> :query_vec AS distance
            FROM code_embeddings
            WHERE project_id = :pid
              AND embedding IS NOT NULL
            ORDER BY embedding <=> :query_vec
            LIMIT :lim
        """)
        result = await db.execute(
            stmt,
            {"query_vec": str(query_embedding), "pid": pid, "lim": limit},
        )
        rows = result.fetchall()
        return [
            {
                "id": str(row.id),
                "file_path": row.file_path,
                "code_unit_type": row.code_unit_type,
                "code_unit_name": row.code_unit_name,
                "distance": row.distance,
                "metadata": row.metadata,
            }
            for row in rows
        ]

    async def delete_file_embeddings(
        self, db: AsyncSession, project_id: uuid.UUID | str, file_path: str
    ) -> None:
        """Remove all embeddings for a given file."""
        pid = uuid.UUID(str(project_id)) if not isinstance(project_id, uuid.UUID) else project_id
        await db.execute(
            delete(CodeEmbedding).where(
                CodeEmbedding.project_id == pid,
                CodeEmbedding.file_path == file_path,
            )
        )
