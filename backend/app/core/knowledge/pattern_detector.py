"""Pattern detection engine — analyzes indexed graph data to detect codebase patterns."""

from __future__ import annotations

import re
import uuid
from collections import Counter, defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.knowledge.graph_manager import KnowledgeGraphManager

# ---- naming heuristics ----

_CASING_PATTERNS = {
    "snake_case": re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)+$"),
    "camelCase": re.compile(r"^[a-z][a-zA-Z0-9]*$"),
    "PascalCase": re.compile(r"^[A-Z][a-zA-Z0-9]*$"),
    "UPPER_SNAKE": re.compile(r"^[A-Z][A-Z0-9]*(_[A-Z0-9]+)+$"),
}

_PREFIX_GROUPS = {
    "getter": re.compile(r"^get[_A-Z]"),
    "setter": re.compile(r"^set[_A-Z]"),
    "fetch": re.compile(r"^fetch[_A-Z]"),
    "create": re.compile(r"^create[_A-Z]"),
    "delete": re.compile(r"^delete[_A-Z]"),
    "update": re.compile(r"^update[_A-Z]"),
    "handle": re.compile(r"^handle[_A-Z]"),
    "on_event": re.compile(r"^on[_A-Z]"),
    "is_check": re.compile(r"^is[_A-Z]"),
    "has_check": re.compile(r"^has[_A-Z]"),
    "use_hook": re.compile(r"^use[A-Z]"),
    "test": re.compile(r"^test[_A-Z]"),
    "private": re.compile(r"^_[a-z]"),
}

_SUFFIX_PATTERNS = {
    "Service": re.compile(r"Service\.(ts|js|py)$"),
    "Controller": re.compile(r"Controller\.(ts|js|py)$"),
    "Repository": re.compile(r"Repositor(y|ies)\.(ts|js|py)$"),
    "Model": re.compile(r"Model\.(ts|js|py)$"),
    "Hook": re.compile(r"Hook\.(ts|js|tsx)$"),
    "Test": re.compile(r"(test_|\.test\.|\.spec\.)", re.IGNORECASE),
    "Router": re.compile(r"(router|route)\.(ts|js|py)$", re.IGNORECASE),
    "Middleware": re.compile(r"middleware\.(ts|js|py)$", re.IGNORECASE),
}

_LAYER_HINTS = {
    "presentation": {"controller", "handler", "route", "router", "view", "page", "component"},
    "business": {"service", "usecase", "use_case", "interactor", "manager"},
    "data": {"repository", "repo", "dao", "store", "adapter", "gateway"},
    "infrastructure": {"config", "middleware", "util", "helper", "lib", "common"},
    "domain": {"model", "entity", "schema", "enum", "type", "interface"},
}

CONVENTION_THRESHOLD = 0.60  # 60% frequency = convention


def _detect_casing(name: str) -> str | None:
    for style, pattern in _CASING_PATTERNS.items():
        if pattern.match(name):
            return style
    return None


def _dir_from_path(file_path: str) -> str:
    """Extract the first meaningful directory segment from a file path."""
    parts = file_path.replace("\\", "/").strip("/").split("/")
    # Skip root-level files or single-depth
    if len(parts) <= 1:
        return "root"
    return parts[-2] if len(parts) >= 2 else parts[0]


class PatternDetector:
    """Analyzes indexed graph data to detect codebase patterns."""

    def __init__(self, graph: KnowledgeGraphManager) -> None:
        self._graph = graph

    # ---- 1. Naming patterns ----

    async def detect_naming_patterns(self, project_id: str) -> list[dict]:
        """Detect naming conventions from function names and file names."""
        functions = await self._graph.query_project_functions(project_id)
        files = await self._graph.query_project_files(project_id)
        if not functions:
            return []

        patterns: list[dict] = []

        # --- Function casing ---
        casing_counts: Counter = Counter()
        casing_examples: dict[str, list[str]] = defaultdict(list)
        for fn in functions:
            style = _detect_casing(fn["name"])
            if style:
                casing_counts[style] += 1
                if len(casing_examples[style]) < 5:
                    casing_examples[style].append(fn["name"])

        total_classified = sum(casing_counts.values())
        if total_classified:
            dominant_style, dominant_count = casing_counts.most_common(1)[0]
            confidence = dominant_count / total_classified
            if confidence >= CONVENTION_THRESHOLD:
                pattern_id = str(uuid.uuid4())
                await self._graph.upsert_pattern(
                    project_id=project_id,
                    pattern_id=pattern_id,
                    name=f"function_{dominant_style}",
                    category="naming",
                    description=f"Functions use {dominant_style} ({confidence:.0%} of {total_classified})",
                    confidence=round(confidence, 3),
                    metadata={
                        "style": dominant_style,
                        "examples": casing_examples[dominant_style],
                        "distribution": dict(casing_counts),
                    },
                )
                # Link matching functions
                matching_ids = [
                    fn["id"] for fn in functions
                    if _detect_casing(fn["name"]) == dominant_style and fn["id"]
                ]
                if matching_ids:
                    await self._graph.link_pattern_to_functions(pattern_id, matching_ids)
                patterns.append({"id": pattern_id, "name": f"function_{dominant_style}", "category": "naming"})

        # --- Prefix conventions ---
        prefix_counts: Counter = Counter()
        prefix_fn_ids: dict[str, list[str]] = defaultdict(list)
        for fn in functions:
            for prefix_name, regex in _PREFIX_GROUPS.items():
                if regex.match(fn["name"]):
                    prefix_counts[prefix_name] += 1
                    prefix_fn_ids[prefix_name].append(fn["id"])
                    break

        for prefix_name, count in prefix_counts.items():
            if count >= 3:  # At least 3 instances
                pattern_id = str(uuid.uuid4())
                await self._graph.upsert_pattern(
                    project_id=project_id,
                    pattern_id=pattern_id,
                    name=f"prefix_{prefix_name}",
                    category="naming",
                    description=f"{count} functions use '{prefix_name}' prefix pattern",
                    confidence=round(count / len(functions), 3),
                    metadata={"count": count, "prefix": prefix_name},
                )
                if prefix_fn_ids[prefix_name]:
                    await self._graph.link_pattern_to_functions(
                        pattern_id, prefix_fn_ids[prefix_name]
                    )
                patterns.append({"id": pattern_id, "name": f"prefix_{prefix_name}", "category": "naming"})

        # --- File suffix conventions ---
        suffix_counts: Counter = Counter()
        suffix_file_ids: dict[str, list[str]] = defaultdict(list)
        for f in files:
            for suffix_name, regex in _SUFFIX_PATTERNS.items():
                if regex.search(f["path"] or ""):
                    suffix_counts[suffix_name] += 1
                    suffix_file_ids[suffix_name].append(f["id"])
                    break

        for suffix_name, count in suffix_counts.items():
            if count >= 2:
                conv_id = str(uuid.uuid4())
                await self._graph.upsert_convention(
                    project_id=project_id,
                    convention_id=conv_id,
                    name=f"file_suffix_{suffix_name}",
                    category="naming",
                    description=f"{count} files follow {suffix_name} suffix pattern",
                    rule=f"Files of this type should use the {suffix_name} suffix",
                    severity="info",
                    metadata={"count": count, "suffix": suffix_name},
                )
                if suffix_file_ids[suffix_name]:
                    await self._graph.link_convention_to_files(
                        conv_id, suffix_file_ids[suffix_name]
                    )
                patterns.append({"id": conv_id, "name": f"file_suffix_{suffix_name}", "category": "naming"})

        return patterns

    # ---- 2. Architecture patterns ----

    async def detect_architecture_patterns(self, project_id: str) -> list[dict]:
        """Detect architectural patterns from directory structure and imports."""
        files = await self._graph.query_project_files(project_id)
        if not files:
            return []

        patterns: list[dict] = []

        # Map directories to layers
        dir_files: dict[str, list[dict]] = defaultdict(list)
        for f in files:
            d = _dir_from_path(f["path"] or "")
            dir_files[d].append(f)

        layer_assignments: dict[str, str] = {}
        for dir_name, dir_file_list in dir_files.items():
            dir_lower = dir_name.lower()
            for layer_name, keywords in _LAYER_HINTS.items():
                if any(kw in dir_lower for kw in keywords):
                    layer_assignments[dir_name] = layer_name
                    break

        # Create layer nodes and link files
        layers_created: dict[str, str] = {}
        for dir_name, layer_name in layer_assignments.items():
            if layer_name not in layers_created:
                layer_id = f"{project_id}::layer::{layer_name}"
                await self._graph.upsert_layer(
                    project_id=project_id,
                    layer_id=layer_id,
                    name=layer_name,
                    description=f"{layer_name.title()} layer",
                )
                layers_created[layer_name] = layer_id

            file_ids = [f["id"] for f in dir_files[dir_name] if f["id"]]
            if file_ids:
                conv_id = str(uuid.uuid4())
                await self._graph.upsert_convention(
                    project_id=project_id,
                    convention_id=conv_id,
                    name=f"layer_{layer_name}_{dir_name}",
                    category="architecture",
                    description=f"Directory '{dir_name}' belongs to {layer_name} layer",
                    rule=f"Files in {dir_name}/ should contain {layer_name} logic",
                    severity="warning",
                    metadata={"directory": dir_name, "layer": layer_name},
                )
                await self._graph.link_convention_to_files(conv_id, file_ids)

        # Detect architectural style
        layer_set = set(layers_created.keys())
        style = "unknown"
        if {"presentation", "business", "data"} <= layer_set:
            style = "layered (MVC-like)"
        elif {"domain", "infrastructure"} <= layer_set:
            style = "clean architecture"
        elif len(layer_set) >= 2:
            style = "modular"

        if layers_created:
            pattern_id = str(uuid.uuid4())
            await self._graph.upsert_pattern(
                project_id=project_id,
                pattern_id=pattern_id,
                name=f"architecture_{style.replace(' ', '_').replace('-', '_')}",
                category="architecture",
                description=f"Detected architecture: {style} ({len(layers_created)} layers)",
                confidence=round(len(layer_assignments) / max(len(dir_files), 1), 3),
                metadata={
                    "style": style,
                    "layers": list(layers_created.keys()),
                    "directory_mapping": layer_assignments,
                },
            )
            patterns.append({"id": pattern_id, "name": f"architecture_{style}", "category": "architecture"})

        return patterns

    # ---- 3. Error handling patterns ----

    async def detect_error_patterns(self, project_id: str) -> list[dict]:
        """Detect error handling patterns from function metadata."""
        functions = await self._graph.query_project_functions(project_id)
        if not functions:
            return []

        patterns: list[dict] = []
        error_indicators = {
            "try_except": 0,
            "custom_exception": 0,
            "result_pattern": 0,
            "http_exception": 0,
        }
        error_fn_ids: dict[str, list[str]] = defaultdict(list)

        for fn in functions:
            name = (fn["name"] or "").lower()
            docstring = (fn["docstring"] or "").lower()
            decorators = fn.get("decorators") or []

            if "error" in name or "exception" in name:
                error_indicators["custom_exception"] += 1
                error_fn_ids["custom_exception"].append(fn["id"])
            if "result" in (fn.get("return_type") or "").lower():
                error_indicators["result_pattern"] += 1
                error_fn_ids["result_pattern"].append(fn["id"])
            if "httpexception" in docstring or "raise" in docstring:
                error_indicators["http_exception"] += 1
                error_fn_ids["http_exception"].append(fn["id"])
            if any("error_handler" in d for d in decorators):
                error_indicators["try_except"] += 1
                error_fn_ids["try_except"].append(fn["id"])

        # Find dominant error handling strategy
        total = sum(error_indicators.values())
        if total >= 3:
            dominant, count = max(error_indicators.items(), key=lambda x: x[1])
            if count >= 2:
                pattern_id = str(uuid.uuid4())
                await self._graph.upsert_pattern(
                    project_id=project_id,
                    pattern_id=pattern_id,
                    name=f"error_{dominant}",
                    category="error_handling",
                    description=f"Dominant error pattern: {dominant} ({count} occurrences)",
                    confidence=round(count / max(total, 1), 3),
                    metadata={"distribution": error_indicators, "dominant": dominant},
                )
                if error_fn_ids[dominant]:
                    await self._graph.link_pattern_to_functions(
                        pattern_id, error_fn_ids[dominant]
                    )
                patterns.append({"id": pattern_id, "name": f"error_{dominant}", "category": "error_handling"})

        return patterns

    # ---- 4. Data access patterns ----

    async def detect_data_access_patterns(self, project_id: str) -> list[dict]:
        """Detect data access patterns (repository, ORM, inline queries)."""
        functions = await self._graph.query_project_functions(project_id)
        files = await self._graph.query_project_files(project_id)
        if not functions:
            return []

        patterns: list[dict] = []
        strategy_counts: Counter = Counter()
        strategy_fn_ids: dict[str, list[str]] = defaultdict(list)

        for fn in functions:
            name = (fn["name"] or "").lower()
            file_path = (fn["file_path"] or "").lower()

            if "repository" in file_path or "repo" in file_path:
                strategy_counts["repository_pattern"] += 1
                strategy_fn_ids["repository_pattern"].append(fn["id"])
            elif "model" in file_path or "orm" in file_path:
                strategy_counts["orm_pattern"] += 1
                strategy_fn_ids["orm_pattern"].append(fn["id"])
            elif any(kw in name for kw in ("query", "sql", "execute", "fetch_all", "fetch_one")):
                strategy_counts["inline_query"] += 1
                strategy_fn_ids["inline_query"].append(fn["id"])

        total = sum(strategy_counts.values())
        if total >= 2:
            dominant, count = strategy_counts.most_common(1)[0]
            pattern_id = str(uuid.uuid4())
            await self._graph.upsert_pattern(
                project_id=project_id,
                pattern_id=pattern_id,
                name=f"data_access_{dominant}",
                category="data_access",
                description=f"Data access: {dominant} ({count} occurrences)",
                confidence=round(count / max(total, 1), 3),
                metadata={"distribution": dict(strategy_counts), "dominant": dominant},
            )
            if strategy_fn_ids[dominant]:
                await self._graph.link_pattern_to_functions(
                    pattern_id, strategy_fn_ids[dominant]
                )
            patterns.append({"id": pattern_id, "name": f"data_access_{dominant}", "category": "data_access"})

        return patterns

    # ---- 5. API patterns ----

    async def detect_api_patterns(self, project_id: str) -> list[dict]:
        """Detect API patterns from route/controller functions."""
        functions = await self._graph.query_project_functions(project_id)
        if not functions:
            return []

        patterns: list[dict] = []
        api_functions = []
        auth_count = 0
        async_count = 0

        http_methods = {"get", "post", "put", "patch", "delete"}

        for fn in functions:
            decorators = fn.get("decorators") or []
            name = (fn["name"] or "").lower()
            file_path = (fn["file_path"] or "").lower()

            is_route = (
                any(d.lower().startswith(("app.", "router.")) for d in decorators)
                or "route" in file_path
                or "controller" in file_path
            )

            if is_route or any(m in name for m in http_methods):
                api_functions.append(fn)
                if fn.get("is_async"):
                    async_count += 1
                if any("auth" in d.lower() or "login" in d.lower() for d in decorators):
                    auth_count += 1

        if not api_functions:
            return []

        # Detect REST conventions
        rest_verbs: Counter = Counter()
        for fn in api_functions:
            name = fn["name"].lower()
            for verb in http_methods:
                if name.startswith(verb) or verb in (fn.get("decorators") or []):
                    rest_verbs[verb] += 1
                    break

        total_api = len(api_functions)

        # Async API pattern
        if async_count > 0:
            async_ratio = async_count / total_api
            pattern_id = str(uuid.uuid4())
            style = "async" if async_ratio >= CONVENTION_THRESHOLD else "mixed"
            await self._graph.upsert_pattern(
                project_id=project_id,
                pattern_id=pattern_id,
                name=f"api_style_{style}",
                category="api",
                description=f"API style: {style} ({async_count}/{total_api} async)",
                confidence=round(async_ratio, 3),
                metadata={
                    "async_count": async_count,
                    "total_api_functions": total_api,
                    "rest_verbs": dict(rest_verbs),
                },
            )
            fn_ids = [fn["id"] for fn in api_functions if fn["id"]]
            if fn_ids:
                await self._graph.link_pattern_to_functions(pattern_id, fn_ids)
            patterns.append({"id": pattern_id, "name": f"api_style_{style}", "category": "api"})

        # Auth pattern
        if auth_count >= 2:
            pattern_id = str(uuid.uuid4())
            await self._graph.upsert_pattern(
                project_id=project_id,
                pattern_id=pattern_id,
                name="api_authenticated",
                category="api",
                description=f"{auth_count}/{total_api} API endpoints use authentication decorators",
                confidence=round(auth_count / total_api, 3),
                metadata={"auth_count": auth_count, "total": total_api},
            )
            patterns.append({"id": pattern_id, "name": "api_authenticated", "category": "api"})

        return patterns
