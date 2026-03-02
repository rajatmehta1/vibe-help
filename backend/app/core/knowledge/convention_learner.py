"""Convention learner — orchestrates pattern detection and provides context-specific lookups."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.knowledge.pattern_detector import PatternDetector, _dir_from_path

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.knowledge.graph_manager import KnowledgeGraphManager

logger = logging.getLogger("forgeline.convention_learner")


class ConventionLearner:
    """Orchestrates all pattern detection and provides convention lookup."""

    def __init__(self, graph: KnowledgeGraphManager, db: AsyncSession) -> None:
        self._graph = graph
        self._db = db
        self._detector = PatternDetector(graph)

    async def learn_all_conventions(self, project_id: str) -> dict:
        """Run all detectors and return an aggregate summary."""
        results: dict[str, list[dict]] = {}

        logger.info("Learning conventions for project %s", project_id)

        results["naming"] = await self._detector.detect_naming_patterns(project_id)
        logger.info("  naming: %d patterns", len(results["naming"]))

        results["architecture"] = await self._detector.detect_architecture_patterns(project_id)
        logger.info("  architecture: %d patterns", len(results["architecture"]))

        results["error_handling"] = await self._detector.detect_error_patterns(project_id)
        logger.info("  error_handling: %d patterns", len(results["error_handling"]))

        results["data_access"] = await self._detector.detect_data_access_patterns(project_id)
        logger.info("  data_access: %d patterns", len(results["data_access"]))

        results["api"] = await self._detector.detect_api_patterns(project_id)
        logger.info("  api: %d patterns", len(results["api"]))

        total_patterns = sum(len(v) for v in results.values())
        logger.info("Convention learning complete: %d total patterns", total_patterns)

        return {
            "project_id": project_id,
            "patterns_count": total_patterns,
            "by_category": {k: len(v) for k, v in results.items()},
            "patterns": results,
        }

    async def get_conventions_for_context(
        self,
        project_id: str,
        file_path: str,
        code_unit_type: str | None = None,
    ) -> list[dict]:
        """Return conventions relevant to a given file path and code unit type.

        Used by the policy engine during real-time analysis.
        """
        conventions = await self._graph.get_conventions(project_id)
        patterns = await self._graph.get_patterns(project_id)

        target_dir = _dir_from_path(file_path)
        relevant: list[dict] = []

        # Filter conventions by directory / layer match
        for conv in conventions:
            meta = conv.get("metadata") or {}
            conv_dir = meta.get("directory", "")
            # Include if convention is about the same directory or is project-wide
            if conv_dir == target_dir or not conv_dir:
                relevant.append({"type": "convention", **conv})

        # Filter patterns by category relevance
        for pat in patterns:
            category = pat.get("category", "")
            # Naming patterns are always relevant
            if category == "naming":
                relevant.append({"type": "pattern", **pat})
            # Error / API patterns relevant to matching code unit type
            elif category == "error_handling" and code_unit_type in ("function", "method"):
                relevant.append({"type": "pattern", **pat})
            elif category == "api" and code_unit_type in ("function", "method"):
                relevant.append({"type": "pattern", **pat})
            elif category == "architecture":
                relevant.append({"type": "pattern", **pat})

        return relevant

    async def get_pattern_evidence(
        self, project_id: str, pattern_id: str
    ) -> list[dict]:
        """Return concrete function examples that follow a specific pattern."""
        functions = await self._graph.query_project_functions(project_id)
        # We need to check which functions are linked to this pattern via Neo4j
        # Use a direct Cypher query for efficiency
        query = """
        MATCH (fn:Function)-[:FOLLOWS_PATTERN]->(pt:Pattern {id: $pattern_id})
        RETURN fn.id AS id, fn.name AS name, fn.line_start AS line_start,
               fn.line_end AS line_end
        """
        async with self._graph._driver.session() as session:
            result = await session.run(query, pattern_id=pattern_id)
            linked = [dict(record) async for record in result]

        if not linked:
            return []

        # Enrich with file path info from the full functions list
        fn_map = {fn["id"]: fn for fn in functions}
        evidence = []
        for link in linked:
            full = fn_map.get(link["id"], {})
            evidence.append({
                "function_name": link["name"],
                "file_path": full.get("file_path", ""),
                "line_start": link["line_start"],
                "line_end": link["line_end"],
                "language": full.get("language", ""),
            })

        return evidence
