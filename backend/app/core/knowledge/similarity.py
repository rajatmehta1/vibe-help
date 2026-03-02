"""Similarity search — combines embedding-based and graph-based code similarity."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.indexer.embedding_builder import EmbeddingBuilder
    from app.core.knowledge.graph_manager import KnowledgeGraphManager


class SimilaritySearch:
    """Hybrid code similarity using pgvector embeddings and Neo4j graph structure."""

    def __init__(
        self,
        graph: KnowledgeGraphManager,
        embedding_builder: EmbeddingBuilder,
        db: AsyncSession,
    ) -> None:
        self._graph = graph
        self._embeddings = embedding_builder
        self._db = db

    async def find_similar_code(
        self,
        project_id: str,
        code_text: str,
        language: str,
        limit: int = 5,
    ) -> list[dict]:
        """Find similar code units by embedding similarity.

        Generates an embedding for the input text and searches pgvector
        for nearest neighbors within the same project.
        """
        embedding = await self._embeddings.generate_embedding(code_text)
        results = await self._embeddings.find_similar(
            db=self._db,
            project_id=project_id,
            embedding=embedding,
            limit=limit,
        )
        return [
            {
                "file_path": r.file_path,
                "code_unit_name": r.code_unit_name,
                "code_unit_type": r.code_unit_type,
                "similarity_score": round(float(r.similarity), 4) if hasattr(r, "similarity") else None,
                "language": language,
            }
            for r in results
        ]

    async def find_similar_functions(
        self,
        project_id: str,
        function_name: str,
        params: list[str] | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """Find similar functions by combining graph name search and embeddings.

        1. Graph search: find functions with similar names in Neo4j.
        2. Embedding search: generate embedding from function signature and search.
        3. Merge and deduplicate, ranked by combined score.
        """
        # --- Graph-based search (name similarity) ---
        graph_query = """
        MATCH (p:Project {id: $project_id})-[:CONTAINS]->(f:File)
              -[:DEFINES]->(fn:Function)
        WHERE toLower(fn.name) CONTAINS toLower($name)
        RETURN fn.id AS id, fn.name AS name, fn.line_start AS line_start,
               f.path AS file_path
        LIMIT $limit
        """
        async with self._graph._driver.session() as session:
            result = await session.run(
                graph_query,
                project_id=project_id,
                name=function_name,
                limit=limit * 2,
            )
            graph_results = [dict(record) async for record in result]

        # --- Embedding-based search ---
        search_text = function_name
        if params:
            search_text += f"({', '.join(params)})"

        embedding = await self._embeddings.generate_embedding(search_text)
        embed_results = await self._embeddings.find_similar(
            db=self._db,
            project_id=project_id,
            embedding=embedding,
            limit=limit * 2,
        )

        # --- Merge and deduplicate ---
        seen: dict[str, dict] = {}

        # Score graph results (1.0 for exact name match, 0.7 for contains)
        for r in graph_results:
            key = r["id"]
            exact = r["name"].lower() == function_name.lower()
            seen[key] = {
                "function_name": r["name"],
                "file_path": r["file_path"],
                "line_start": r["line_start"],
                "graph_score": 1.0 if exact else 0.7,
                "embed_score": 0.0,
            }

        # Score embedding results
        for r in embed_results:
            key = f"{r.file_path}::{r.code_unit_name}"
            sim = float(r.similarity) if hasattr(r, "similarity") else 0.5
            if key in seen:
                seen[key]["embed_score"] = sim
            else:
                seen[key] = {
                    "function_name": r.code_unit_name,
                    "file_path": r.file_path,
                    "line_start": None,
                    "graph_score": 0.0,
                    "embed_score": sim,
                }

        # Combined score: weighted average
        ranked = []
        for entry in seen.values():
            combined = 0.6 * entry["graph_score"] + 0.4 * entry["embed_score"]
            ranked.append({
                "function_name": entry["function_name"],
                "file_path": entry["file_path"],
                "line_start": entry["line_start"],
                "similarity_score": round(combined, 4),
            })

        ranked.sort(key=lambda x: x["similarity_score"], reverse=True)
        return ranked[:limit]
