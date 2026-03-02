"""Neo4j knowledge graph manager for ForgeLine.

Manages the code knowledge graph: files, functions, modules, imports,
call graphs, patterns, conventions, and AI-generation tracking.
"""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

from app.config import settings

logger = logging.getLogger("forgeline.knowledge")


class KnowledgeGraphManager:
    """Async Neo4j knowledge graph manager with connection pooling."""

    def __init__(
        self,
        uri: str = settings.NEO4J_URI,
        user: str = settings.NEO4J_USER,
        password: str = settings.NEO4J_PASSWORD,
    ) -> None:
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(
            uri, auth=(user, password), max_connection_pool_size=50
        )

    async def close(self) -> None:
        await self._driver.close()

    async def verify_connection(self) -> dict[str, Any]:
        async with self._driver.session() as session:
            result = await session.run("RETURN 1 AS ok")
            record = await result.single()
            return {"neo4j": "connected", "result": record["ok"]}

    # ------------------------------------------------------------------
    # Indexes
    # ------------------------------------------------------------------

    async def ensure_indexes(self) -> None:
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (f:File) ON (f.path)",
            "CREATE INDEX IF NOT EXISTS FOR (f:File) ON (f.id)",
            "CREATE INDEX IF NOT EXISTS FOR (fn:Function) ON (fn.name)",
            "CREATE INDEX IF NOT EXISTS FOR (fn:Function) ON (fn.id)",
            "CREATE INDEX IF NOT EXISTS FOR (m:Module) ON (m.name)",
            "CREATE INDEX IF NOT EXISTS FOR (m:Module) ON (m.id)",
            "CREATE INDEX IF NOT EXISTS FOR (p:Package) ON (p.name)",
            "CREATE INDEX IF NOT EXISTS FOR (pt:Pattern) ON (pt.type)",
            "CREATE INDEX IF NOT EXISTS FOR (pt:Pattern) ON (pt.id)",
            "CREATE INDEX IF NOT EXISTS FOR (c:Convention) ON (c.category)",
            "CREATE INDEX IF NOT EXISTS FOR (c:Convention) ON (c.id)",
            "CREATE INDEX IF NOT EXISTS FOR (pr:Project) ON (pr.id)",
            "CREATE INDEX IF NOT EXISTS FOR (v:Variable) ON (v.id)",
            "CREATE INDEX IF NOT EXISTS FOR (i:Interface) ON (i.id)",
            "CREATE INDEX IF NOT EXISTS FOR (l:Layer) ON (l.name)",
            "CREATE INDEX IF NOT EXISTS FOR (a:AIGeneration) ON (a.id)",
        ]
        async with self._driver.session() as session:
            for idx in indexes:
                await session.run(idx)
        logger.info("Neo4j indexes ensured (%d indexes)", len(indexes))

    # ------------------------------------------------------------------
    # Write Operations
    # ------------------------------------------------------------------

    async def upsert_file(self, project_id: str, file_data: dict[str, Any]) -> None:
        query = """
        MERGE (p:Project {id: $project_id})
        MERGE (f:File {id: $file_id})
        SET f += $props
        MERGE (p)-[:CONTAINS]->(f)
        """
        props = {k: v for k, v in file_data.items() if k != "id"}
        async with self._driver.session() as session:
            await session.run(
                query,
                project_id=project_id,
                file_id=file_data["id"],
                props=props,
            )
        logger.debug("Upserted file %s in project %s", file_data.get("path"), project_id)

    async def upsert_code_unit(
        self, file_id: str, unit_type: str, unit_data: dict[str, Any]
    ) -> None:
        label = unit_type.capitalize()
        if label not in ("Function", "Module", "Variable", "Interface"):
            raise ValueError(f"Invalid unit_type: {unit_type}")

        query = f"""
        MERGE (u:{label} {{id: $unit_id}})
        SET u += $props
        WITH u
        MATCH (f:File {{id: $file_id}})
        MERGE (f)-[:DEFINES]->(u)
        """
        props = {k: v for k, v in unit_data.items() if k != "id"}
        async with self._driver.session() as session:
            await session.run(
                query,
                unit_id=unit_data["id"],
                file_id=file_id,
                props=props,
            )
        logger.debug("Upserted %s %s in file %s", label, unit_data.get("name"), file_id)

    async def set_relationships(
        self,
        file_id: str,
        imports: list[dict[str, Any]] | None = None,
        calls: list[dict[str, Any]] | None = None,
        extends: list[dict[str, Any]] | None = None,
        implements: list[dict[str, Any]] | None = None,
    ) -> None:
        async with self._driver.session() as session:
            if imports:
                await session.run(
                    """
                    UNWIND $imports AS imp
                    MATCH (src:File {id: $file_id})
                    MATCH (tgt:File {id: imp.target_file_id})
                    MERGE (src)-[r:IMPORTS]->(tgt)
                    SET r.imported_names = imp.imported_names
                    """,
                    file_id=file_id,
                    imports=imports,
                )

            if calls:
                await session.run(
                    """
                    UNWIND $calls AS c
                    MATCH (caller:Function {id: c.caller_id})
                    MATCH (callee:Function {id: c.callee_id})
                    MERGE (caller)-[:CALLS]->(callee)
                    """,
                    calls=calls,
                )

            if extends:
                await session.run(
                    """
                    UNWIND $extends AS e
                    MATCH (child:Module {id: e.child_id})
                    MATCH (parent:Module {id: e.parent_id})
                    MERGE (child)-[:EXTENDS]->(parent)
                    """,
                    extends=extends,
                )

            if implements:
                await session.run(
                    """
                    UNWIND $implements AS impl
                    MATCH (m:Module {id: impl.module_id})
                    MATCH (i:Interface {id: impl.interface_id})
                    MERGE (m)-[:IMPLEMENTS]->(i)
                    """,
                    implements=implements,
                )

        logger.debug("Set relationships for file %s", file_id)

    async def set_dependencies(
        self, file_id: str, packages: list[dict[str, Any]]
    ) -> None:
        query = """
        UNWIND $packages AS pkg
        MERGE (p:Package {name: pkg.name})
        SET p.version = pkg.version, p.license = pkg.license, p.source = pkg.source
        WITH p, pkg
        MATCH (f:File {id: $file_id})
        MERGE (f)-[r:DEPENDS_ON]->(p)
        SET r.version_constraint = pkg.version_constraint
        """
        async with self._driver.session() as session:
            await session.run(query, file_id=file_id, packages=packages)
        logger.debug("Set %d dependencies for file %s", len(packages), file_id)

    async def mark_ai_generated(
        self, function_id: str, source: str, confidence: float
    ) -> None:
        query = """
        MATCH (fn:Function {id: $function_id})
        MERGE (a:AIGeneration {id: $function_id + '_aigen'})
        SET a.source = $source,
            a.confidence = $confidence,
            a.timestamp = datetime(),
            a.review_status = 'pending'
        MERGE (fn)-[:GENERATED_BY]->(a)
        """
        async with self._driver.session() as session:
            await session.run(
                query,
                function_id=function_id,
                source=source,
                confidence=confidence,
            )
        logger.debug("Marked function %s as AI-generated (source=%s)", function_id, source)

    async def upsert_pattern(self, pattern_data: dict[str, Any]) -> None:
        query = """
        MERGE (p:Pattern {id: $pattern_id})
        SET p += $props,
            p.last_updated = datetime()
        ON CREATE SET p.first_detected = datetime()
        """
        props = {k: v for k, v in pattern_data.items() if k != "id"}
        async with self._driver.session() as session:
            await session.run(query, pattern_id=pattern_data["id"], props=props)
        logger.debug("Upserted pattern %s", pattern_data.get("name"))

    async def upsert_convention(self, convention_data: dict[str, Any]) -> None:
        query = """
        MERGE (c:Convention {id: $conv_id})
        SET c += $props
        """
        props = {k: v for k, v in convention_data.items() if k != "id"}
        async with self._driver.session() as session:
            await session.run(query, conv_id=convention_data["id"], props=props)
        logger.debug("Upserted convention %s", convention_data.get("category"))

    async def set_layer(self, module_id: str, layer_name: str) -> None:
        query = """
        MATCH (m:Module {id: $module_id})
        MERGE (l:Layer {name: $layer_name})
        MERGE (m)-[:BELONGS_TO_LAYER]->(l)
        """
        async with self._driver.session() as session:
            await session.run(query, module_id=module_id, layer_name=layer_name)
        logger.debug("Set layer %s for module %s", layer_name, module_id)

    async def delete_file_subgraph(self, file_id: str) -> None:
        query = """
        MATCH (f:File {id: $file_id})
        OPTIONAL MATCH (f)-[:DEFINES]->(unit)
        DETACH DELETE unit
        DETACH DELETE f
        """
        async with self._driver.session() as session:
            await session.run(query, file_id=file_id)
        logger.info("Deleted file subgraph %s", file_id)

    async def clear_project(self, project_id: str) -> None:
        query = """
        MATCH (p:Project {id: $project_id})-[:CONTAINS]->(f:File)
        OPTIONAL MATCH (f)-[:DEFINES]->(unit)
        DETACH DELETE unit
        DETACH DELETE f
        DETACH DELETE p
        """
        async with self._driver.session() as session:
            await session.run(query, project_id=project_id)
        logger.info("Cleared project graph %s", project_id)

    # ------------------------------------------------------------------
    # Read Operations
    # ------------------------------------------------------------------

    async def get_project_stats(self, project_id: str) -> dict[str, Any]:
        query = """
        MATCH (p:Project {id: $project_id})-[:CONTAINS]->(f:File)
        OPTIONAL MATCH (f)-[:DEFINES]->(fn:Function)
        OPTIONAL MATCH (f)-[:DEFINES]->(m:Module)
        OPTIONAL MATCH (f)-[:DEPENDS_ON]->(pkg:Package)
        OPTIONAL MATCH (fn)-[:GENERATED_BY]->(a:AIGeneration)
        WITH p,
             count(DISTINCT f) AS file_count,
             count(DISTINCT fn) AS function_count,
             count(DISTINCT m) AS module_count,
             count(DISTINCT pkg) AS package_count,
             count(DISTINCT a) AS ai_generated_count
        OPTIONAL MATCH (pt:Pattern)--(any_node)--(:File)<-[:CONTAINS]-(p)
        WITH file_count, function_count, module_count, package_count,
             ai_generated_count, count(DISTINCT pt) AS pattern_count
        RETURN file_count, function_count, module_count, package_count,
               pattern_count, ai_generated_count,
               CASE WHEN function_count > 0
                    THEN toFloat(ai_generated_count) / function_count
                    ELSE 0.0 END AS ai_generated_ratio
        """
        async with self._driver.session() as session:
            result = await session.run(query, project_id=project_id)
            record = await result.single()
            if not record:
                return {
                    "file_count": 0,
                    "function_count": 0,
                    "module_count": 0,
                    "package_count": 0,
                    "pattern_count": 0,
                    "convention_count": 0,
                    "ai_generated_ratio": 0.0,
                }
            data = dict(record)
            # Add convention count separately for cleaner query
            conv_result = await session.run(
                """
                MATCH (p:Project {id: $project_id})-[:CONTAINS]->(f:File)-[:EVIDENCE_OF]->(c:Convention)
                RETURN count(DISTINCT c) AS convention_count
                """,
                project_id=project_id,
            )
            conv_record = await conv_result.single()
            data["convention_count"] = conv_record["convention_count"] if conv_record else 0
            return data

    async def get_file_graph(self, file_id: str) -> dict[str, Any]:
        query = """
        MATCH (f:File {id: $file_id})
        OPTIONAL MATCH (f)-[:DEFINES]->(unit)
        OPTIONAL MATCH (f)-[imp:IMPORTS]->(imported:File)
        OPTIONAL MATCH (f)-[dep:DEPENDS_ON]->(pkg:Package)
        RETURN f AS file,
               collect(DISTINCT unit) AS units,
               collect(DISTINCT {file: imported, imported_names: imp.imported_names}) AS imports,
               collect(DISTINCT {package: pkg, version_constraint: dep.version_constraint}) AS dependencies
        """
        async with self._driver.session() as session:
            result = await session.run(query, file_id=file_id)
            record = await result.single()
            if not record:
                return {}
            return {
                "file": dict(record["file"]) if record["file"] else None,
                "units": [dict(u) for u in record["units"] if u],
                "imports": [
                    {
                        "file": dict(i["file"]) if i["file"] else None,
                        "imported_names": i["imported_names"],
                    }
                    for i in record["imports"]
                    if i["file"]
                ],
                "dependencies": [
                    {
                        "package": dict(d["package"]) if d["package"] else None,
                        "version_constraint": d["version_constraint"],
                    }
                    for d in record["dependencies"]
                    if d["package"]
                ],
            }

    async def get_function_callers(self, function_id: str) -> list[dict[str, Any]]:
        query = """
        MATCH (caller:Function)-[:CALLS]->(fn:Function {id: $function_id})
        OPTIONAL MATCH (f:File)-[:DEFINES]->(caller)
        RETURN caller AS function, f.path AS file_path
        """
        async with self._driver.session() as session:
            result = await session.run(query, function_id=function_id)
            records = [record async for record in result]
            return [
                {"function": dict(r["function"]), "file_path": r["file_path"]}
                for r in records
            ]

    async def get_function_callees(self, function_id: str) -> list[dict[str, Any]]:
        query = """
        MATCH (fn:Function {id: $function_id})-[:CALLS]->(callee:Function)
        OPTIONAL MATCH (f:File)-[:DEFINES]->(callee)
        RETURN callee AS function, f.path AS file_path
        """
        async with self._driver.session() as session:
            result = await session.run(query, function_id=function_id)
            records = [record async for record in result]
            return [
                {"function": dict(r["function"]), "file_path": r["file_path"]}
                for r in records
            ]

    async def get_import_graph(self, project_id: str) -> list[dict[str, Any]]:
        query = """
        MATCH (p:Project {id: $project_id})-[:CONTAINS]->(src:File)-[imp:IMPORTS]->(tgt:File)
        RETURN src.path AS source, tgt.path AS target,
               imp.imported_names AS imported_names
        """
        async with self._driver.session() as session:
            result = await session.run(query, project_id=project_id)
            records = [record async for record in result]
            return [dict(r) for r in records]

    async def get_dependency_tree(self, project_id: str) -> list[dict[str, Any]]:
        query = """
        MATCH (p:Project {id: $project_id})-[:CONTAINS]->(f:File)-[dep:DEPENDS_ON]->(pkg:Package)
        RETURN pkg.name AS package_name, pkg.version AS version,
               pkg.license AS license, pkg.source AS source,
               collect(DISTINCT f.path) AS dependent_files
        ORDER BY pkg.name
        """
        async with self._driver.session() as session:
            result = await session.run(query, project_id=project_id)
            records = [record async for record in result]
            return [dict(r) for r in records]

    async def get_similar_functions(
        self, project_id: str, function_name: str, function_params: str | None = None
    ) -> list[dict[str, Any]]:
        query = """
        MATCH (p:Project {id: $project_id})-[:CONTAINS]->(f:File)-[:DEFINES]->(fn:Function)
        WHERE fn.name CONTAINS $name_fragment
           OR fn.name =~ $name_pattern
        RETURN fn AS function, f.path AS file_path
        ORDER BY fn.name
        LIMIT 20
        """
        # Build a fuzzy pattern: split camelCase/snake_case parts
        parts = function_name.replace("_", " ").split()
        pattern = "(?i).*" + ".*".join(parts) + ".*"
        async with self._driver.session() as session:
            result = await session.run(
                query,
                project_id=project_id,
                name_fragment=function_name,
                name_pattern=pattern,
            )
            records = [record async for record in result]
            return [
                {"function": dict(r["function"]), "file_path": r["file_path"]}
                for r in records
            ]

    async def get_patterns(
        self, project_id: str, pattern_type: str | None = None
    ) -> list[dict[str, Any]]:
        if pattern_type:
            query = """
            MATCH (fn:Function)-[:FOLLOWS_PATTERN]->(pt:Pattern {type: $pattern_type})
            MATCH (f:File)-[:DEFINES]->(fn)
            MATCH (p:Project {id: $project_id})-[:CONTAINS]->(f)
            RETURN DISTINCT pt AS pattern
            ORDER BY pt.name
            """
            params: dict[str, Any] = {"project_id": project_id, "pattern_type": pattern_type}
        else:
            query = """
            MATCH (fn:Function)-[:FOLLOWS_PATTERN]->(pt:Pattern)
            MATCH (f:File)-[:DEFINES]->(fn)
            MATCH (p:Project {id: $project_id})-[:CONTAINS]->(f)
            RETURN DISTINCT pt AS pattern
            ORDER BY pt.type, pt.name
            """
            params = {"project_id": project_id}

        async with self._driver.session() as session:
            result = await session.run(query, **params)
            records = [record async for record in result]
            return [dict(r["pattern"]) for r in records]

    async def get_conventions(
        self, project_id: str, category: str | None = None
    ) -> list[dict[str, Any]]:
        if category:
            query = """
            MATCH (p:Project {id: $project_id})-[:CONTAINS]->(f:File)-[:EVIDENCE_OF]->(c:Convention {category: $category})
            RETURN DISTINCT c AS convention
            ORDER BY c.category
            """
            params: dict[str, Any] = {"project_id": project_id, "category": category}
        else:
            query = """
            MATCH (p:Project {id: $project_id})-[:CONTAINS]->(f:File)-[:EVIDENCE_OF]->(c:Convention)
            RETURN DISTINCT c AS convention
            ORDER BY c.category
            """
            params = {"project_id": project_id}

        async with self._driver.session() as session:
            result = await session.run(query, **params)
            records = [record async for record in result]
            return [dict(r["convention"]) for r in records]

    async def get_layer_violations(
        self, project_id: str, layer_rules: list[dict[str, str]]
    ) -> list[dict[str, Any]]:
        """Find layer violations.

        layer_rules: [{"from_layer": "controllers", "forbidden_layer": "repositories"}]
        """
        violations: list[dict[str, Any]] = []
        query = """
        MATCH (p:Project {id: $project_id})-[:CONTAINS]->(f:File)-[:DEFINES]->(m:Module)
              -[:BELONGS_TO_LAYER]->(src_layer:Layer {name: $from_layer})
        MATCH (f)-[:IMPORTS]->(f2:File)-[:DEFINES]->(m2:Module)
              -[:BELONGS_TO_LAYER]->(tgt_layer:Layer {name: $forbidden_layer})
        RETURN m.name AS source_module, src_layer.name AS source_layer,
               m2.name AS target_module, tgt_layer.name AS target_layer,
               f.path AS source_file, f2.path AS target_file
        """
        async with self._driver.session() as session:
            for rule in layer_rules:
                result = await session.run(
                    query,
                    project_id=project_id,
                    from_layer=rule["from_layer"],
                    forbidden_layer=rule["forbidden_layer"],
                )
                records = [record async for record in result]
                violations.extend(dict(r) for r in records)
        return violations

    async def get_ai_generated_code(
        self, project_id: str, reviewed: bool | None = None
    ) -> list[dict[str, Any]]:
        review_filter = ""
        if reviewed is True:
            review_filter = "AND a.review_status = 'reviewed'"
        elif reviewed is False:
            review_filter = "AND a.review_status = 'pending'"

        query = f"""
        MATCH (p:Project {{id: $project_id}})-[:CONTAINS]->(f:File)-[:DEFINES]->(fn:Function)
              -[:GENERATED_BY]->(a:AIGeneration)
        WHERE true {review_filter}
        RETURN fn AS function, f.path AS file_path,
               a.source AS ai_source, a.confidence AS confidence,
               a.review_status AS review_status, a.timestamp AS timestamp
        ORDER BY a.timestamp DESC
        """
        async with self._driver.session() as session:
            result = await session.run(query, project_id=project_id)
            records = [record async for record in result]
            return [
                {
                    "function": dict(r["function"]),
                    "file_path": r["file_path"],
                    "ai_source": r["ai_source"],
                    "confidence": r["confidence"],
                    "review_status": r["review_status"],
                    "timestamp": str(r["timestamp"]) if r["timestamp"] else None,
                }
                for r in records
            ]

    async def find_circular_dependencies(self, project_id: str) -> list[list[str]]:
        query = """
        MATCH (p:Project {id: $project_id})-[:CONTAINS]->(f:File)
        MATCH path = (f)-[:IMPORTS*2..10]->(f)
        WITH [node IN nodes(path) | node.path] AS cycle
        WITH cycle, cycle[0] AS first
        WHERE ALL(i IN range(1, size(cycle)-2) WHERE cycle[i] > first)
        RETURN DISTINCT cycle
        LIMIT 50
        """
        async with self._driver.session() as session:
            result = await session.run(query, project_id=project_id)
            records = [record async for record in result]
            return [r["cycle"] for r in records]

    async def get_architectural_overview(self, project_id: str) -> dict[str, Any]:
        layers_query = """
        MATCH (p:Project {id: $project_id})-[:CONTAINS]->(f:File)-[:DEFINES]->(m:Module)
              -[:BELONGS_TO_LAYER]->(l:Layer)
        RETURN l.name AS layer_name, l.description AS description,
               collect(DISTINCT m.name) AS modules,
               count(DISTINCT m) AS module_count
        ORDER BY l.name
        """
        cross_query = """
        MATCH (p:Project {id: $project_id})-[:CONTAINS]->(f1:File)-[:DEFINES]->(m1:Module)
              -[:BELONGS_TO_LAYER]->(l1:Layer)
        MATCH (f1)-[:IMPORTS]->(f2:File)-[:DEFINES]->(m2:Module)
              -[:BELONGS_TO_LAYER]->(l2:Layer)
        WHERE l1 <> l2
        RETURN l1.name AS from_layer, l2.name AS to_layer,
               count(*) AS relationship_count
        ORDER BY relationship_count DESC
        """
        async with self._driver.session() as session:
            layers_result = await session.run(layers_query, project_id=project_id)
            layers_records = [record async for record in layers_result]

            cross_result = await session.run(cross_query, project_id=project_id)
            cross_records = [record async for record in cross_result]

        return {
            "layers": [
                {
                    "name": r["layer_name"],
                    "description": r["description"],
                    "modules": r["modules"],
                    "module_count": r["module_count"],
                }
                for r in layers_records
            ],
            "cross_layer_relationships": [
                {
                    "from_layer": r["from_layer"],
                    "to_layer": r["to_layer"],
                    "count": r["relationship_count"],
                }
                for r in cross_records
            ],
        }

    # ---- bulk query methods (for pattern detection) ----

    async def query_project_functions(self, project_id: str) -> list[dict]:
        """Return all functions in a project with their file paths."""
        query = """
        MATCH (p:Project {id: $project_id})-[:CONTAINS]->(f:File)
              -[:DEFINES]->(fn:Function)
        RETURN fn.id AS id, fn.name AS name, fn.line_start AS line_start,
               fn.line_end AS line_end, fn.is_async AS is_async,
               fn.is_exported AS is_exported, fn.complexity AS complexity,
               fn.docstring AS docstring, fn.return_type AS return_type,
               fn.param_names AS param_names, fn.decorators AS decorators,
               f.path AS file_path, f.language AS language
        """
        async with self._driver.session() as session:
            result = await session.run(query, project_id=project_id)
            return [dict(record) async for record in result]

    async def query_project_files(self, project_id: str) -> list[dict]:
        """Return all files in a project."""
        query = """
        MATCH (p:Project {id: $project_id})-[:CONTAINS]->(f:File)
        RETURN f.id AS id, f.path AS path, f.language AS language,
               f.lines_of_code AS lines_of_code
        """
        async with self._driver.session() as session:
            result = await session.run(query, project_id=project_id)
            return [dict(record) async for record in result]

    async def link_pattern_to_functions(
        self, pattern_id: str, function_ids: list[str]
    ) -> None:
        """Create FOLLOWS_PATTERN relationships from functions to a pattern."""
        query = """
        UNWIND $function_ids AS fid
        MATCH (fn:Function {id: fid}), (pt:Pattern {id: $pattern_id})
        MERGE (fn)-[:FOLLOWS_PATTERN]->(pt)
        """
        async with self._driver.session() as session:
            await session.run(
                query, pattern_id=pattern_id, function_ids=function_ids
            )

    async def link_convention_to_files(
        self, convention_id: str, file_ids: list[str]
    ) -> None:
        """Create EVIDENCE_OF relationships from files to a convention."""
        query = """
        UNWIND $file_ids AS fid
        MATCH (f:File {id: fid}), (c:Convention {id: $convention_id})
        MERGE (f)-[:EVIDENCE_OF]->(c)
        """
        async with self._driver.session() as session:
            await session.run(
                query, convention_id=convention_id, file_ids=file_ids
            )
