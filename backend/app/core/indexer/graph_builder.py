"""Build the Neo4j knowledge graph from parsed source files."""

from __future__ import annotations

import logging
from typing import Any

from app.core.indexer.parsers.base import ParsedCodeUnit, ParsedFile
from app.core.indexer.parsers.dependency_parser import parse_dependency_file
from app.core.knowledge.graph_manager import KnowledgeGraphManager

logger = logging.getLogger("forgeline.graph_builder")

# KnowledgeGraphManager only accepts these unit_type values.
# "class" from parsers must be mapped to "module".
_UNIT_TYPE_MAP: dict[str, str] = {
    "function": "function",
    "class": "module",
    "interface": "interface",
    "variable": "variable",
    "module": "module",
}


def _make_file_id(project_id: str, file_path: str) -> str:
    """Deterministic file ID: project_id::file_path."""
    return f"{project_id}::{file_path}"


def _make_unit_id(file_id: str, unit_type: str, unit_name: str) -> str:
    """Deterministic code unit ID: file_id::type::name."""
    return f"{file_id}::{unit_type}::{unit_name}"


class GraphBuilder:
    """Translates ParsedFile objects into Neo4j graph via KnowledgeGraphManager."""

    def __init__(self, graph: KnowledgeGraphManager) -> None:
        self._graph = graph

    async def index_file(self, project_id: str, parsed: ParsedFile) -> str:
        """Index a single parsed file into the graph.

        1. Delete existing subgraph for this file
        2. Upsert the File node
        3. Upsert all code units (functions, classes-as-modules, interfaces, variables)
        4. Create IMPORTS relationships to other known files

        Returns the file_id used as the node ID.
        """
        file_id = _make_file_id(project_id, parsed.path)

        # Clean slate for this file
        await self._graph.delete_file_subgraph(file_id)

        # Upsert file node
        file_data: dict[str, Any] = {
            "id": file_id,
            "path": parsed.path,
            "language": parsed.language,
            "lines_of_code": parsed.lines_of_code,
        }
        await self._graph.upsert_file(project_id, file_data)

        # Upsert code units
        for unit in parsed.code_units:
            await self._index_code_unit(file_id, unit)
            # Also index child methods (e.g. class methods) as separate nodes
            for child in unit.children:
                child_name = f"{unit.name}.{child.name}"
                await self._index_code_unit(file_id, child, name_override=child_name)

        # Upsert top-level variables
        for var in parsed.top_level_variables:
            var_id = _make_unit_id(file_id, "variable", var["name"])
            var_data: dict[str, Any] = {
                "id": var_id,
                "name": var["name"],
                "type_annotation": var.get("type_annotation"),
                "is_constant": var.get("is_constant", False),
            }
            await self._graph.upsert_code_unit(file_id, "variable", var_data)

        # Create IMPORTS relationships (best-effort: unresolvable imports silently skipped)
        imports_data: list[dict[str, Any]] = []
        for imp in parsed.imports:
            target_path = self._resolve_import_path(
                parsed.path, imp.source, imp.is_relative
            )
            if target_path:
                target_file_id = _make_file_id(project_id, target_path)
                imports_data.append({
                    "target_file_id": target_file_id,
                    "imported_names": imp.imported_names,
                })

        if imports_data:
            await self._graph.set_relationships(file_id, imports=imports_data)

        logger.debug(
            "Indexed file %s: %d units, %d imports",
            parsed.path,
            len(parsed.code_units),
            len(imports_data),
        )
        return file_id

    async def _index_code_unit(
        self,
        file_id: str,
        unit: ParsedCodeUnit,
        name_override: str | None = None,
    ) -> None:
        """Upsert a single code unit to the graph."""
        graph_type = _UNIT_TYPE_MAP.get(unit.type)
        if graph_type is None:
            logger.warning("Unknown code unit type %r, skipping", unit.type)
            return

        name = name_override or unit.name
        unit_id = _make_unit_id(file_id, unit.type, name)

        unit_data: dict[str, Any] = {
            "id": unit_id,
            "name": name,
            "line_start": unit.line_start,
            "line_end": unit.line_end,
            "is_async": unit.is_async,
            "is_exported": unit.is_exported,
            "complexity": unit.complexity,
        }
        if unit.docstring:
            unit_data["docstring"] = unit.docstring[:500]
        if unit.return_type:
            unit_data["return_type"] = unit.return_type
        if unit.params:
            unit_data["param_names"] = [p["name"] for p in unit.params]
        if unit.decorators:
            unit_data["decorators"] = unit.decorators

        await self._graph.upsert_code_unit(file_id, graph_type, unit_data)

    async def build_call_graph(
        self, project_id: str, all_parsed_files: list[ParsedFile]
    ) -> int:
        """Second-pass: build CALLS edges by matching function calls by name.

        For each function, look at its body_text for references to other
        known function names within the project. This is heuristic
        (name-based, not scope-aware) but effective for most codebases.

        Returns the number of call edges created.
        """
        # Build name -> unit_id lookup for all functions
        func_lookup: dict[str, str] = {}
        file_funcs: list[tuple[str, ParsedCodeUnit]] = []

        for parsed in all_parsed_files:
            file_id = _make_file_id(project_id, parsed.path)
            for unit in parsed.code_units:
                if unit.type == "function":
                    uid = _make_unit_id(file_id, "function", unit.name)
                    func_lookup[unit.name] = uid
                    file_funcs.append((file_id, unit))
                # Methods inside classes
                for child in unit.children:
                    if child.type == "function":
                        full_name = f"{unit.name}.{child.name}"
                        uid = _make_unit_id(file_id, "function", full_name)
                        func_lookup[full_name] = uid
                        file_funcs.append((file_id, child))

        # Scan each function's body for calls to known functions
        call_count = 0
        calls_by_file: dict[str, list[dict[str, str]]] = {}

        for file_id, unit in file_funcs:
            caller_name = unit.name
            caller_id = func_lookup.get(caller_name)
            if not caller_id:
                continue

            for known_name, callee_id in func_lookup.items():
                if known_name == caller_name:
                    continue
                # Heuristic: function name followed by ( in body text
                if f"{known_name}(" in unit.body_text:
                    calls_by_file.setdefault(file_id, []).append({
                        "caller_id": caller_id,
                        "callee_id": callee_id,
                    })
                    call_count += 1

        # Batch set_relationships per file
        for file_id, calls in calls_by_file.items():
            await self._graph.set_relationships(file_id, calls=calls)

        logger.info("Built call graph: %d call edges", call_count)
        return call_count

    async def index_dependencies(
        self, project_id: str, dep_file_path: str, content: str
    ) -> int:
        """Parse and index a dependency manifest file.

        Returns number of packages indexed.
        """
        packages = parse_dependency_file(dep_file_path, content)
        if not packages:
            return 0

        file_id = _make_file_id(project_id, dep_file_path)

        # Upsert the dependency file as a File node
        file_data: dict[str, Any] = {
            "id": file_id,
            "path": dep_file_path,
            "language": "manifest",
            "lines_of_code": content.count("\n") + 1,
        }
        await self._graph.upsert_file(project_id, file_data)

        # Create Package nodes and DEPENDS_ON relationships
        pkg_data: list[dict[str, Any]] = []
        for pkg in packages:
            pkg_data.append({
                "name": pkg["name"],
                "version_constraint": pkg.get("version_constraint"),
                "version": pkg.get("version_constraint"),
                "license": None,
                "source": "manifest",
            })

        await self._graph.set_dependencies(file_id, pkg_data)
        logger.info("Indexed %d dependencies from %s", len(pkg_data), dep_file_path)
        return len(pkg_data)

    def _resolve_import_path(
        self, source_path: str, import_source: str, is_relative: bool
    ) -> str | None:
        """Best-effort resolution of an import source to a file path.

        For relative imports, resolve relative to source_path's directory.
        For absolute imports, convert dotted path to slash path.
        Returns None if resolution is ambiguous.
        """
        if not import_source:
            return None

        if is_relative:
            parts = source_path.replace("\\", "/").rsplit("/", 1)
            directory = parts[0] if len(parts) > 1 else ""
            # Count leading dots
            dots = 0
            for ch in import_source:
                if ch == ".":
                    dots += 1
                else:
                    break
            module_part = import_source[dots:]
            # Go up (dots - 1) directories
            dir_parts = directory.split("/") if directory else []
            for _ in range(dots - 1):
                if dir_parts:
                    dir_parts.pop()
            base = "/".join(dir_parts)
            if module_part:
                resolved = module_part.replace(".", "/")
                return f"{base}/{resolved}" if base else resolved
            return base or None
        else:
            return import_source.replace(".", "/")
