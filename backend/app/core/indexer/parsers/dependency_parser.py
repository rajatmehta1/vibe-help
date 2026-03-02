"""Parser for dependency manifest files (package.json, requirements.txt, pyproject.toml)."""

from __future__ import annotations

import json
import re


def parse_package_json(content: str) -> list[dict]:
    """Parse package.json and return dependency list."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []

    deps: list[dict] = []
    for name, version in (data.get("dependencies") or {}).items():
        deps.append({"name": name, "version_constraint": version, "is_dev_dependency": False})
    for name, version in (data.get("devDependencies") or {}).items():
        deps.append({"name": name, "version_constraint": version, "is_dev_dependency": True})
    return deps


def parse_requirements_txt(content: str) -> list[dict]:
    """Parse requirements.txt and return dependency list."""
    deps: list[dict] = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Handle extras like package[extra]>=1.0
        match = re.match(r"^([a-zA-Z0-9_.-]+(?:\[[a-zA-Z0-9_,.-]+\])?)\s*(.*)", line)
        if match:
            name = match.group(1)
            constraint = match.group(2).strip()
            # Remove comments
            if "#" in constraint:
                constraint = constraint[: constraint.index("#")].strip()
            deps.append({
                "name": name,
                "version_constraint": constraint or None,
                "is_dev_dependency": False,
            })
    return deps


def parse_pyproject_toml(content: str) -> list[dict]:
    """Parse pyproject.toml dependencies.

    Uses basic string parsing to avoid requiring a toml library.
    """
    deps: list[dict] = []
    in_deps = False
    in_dev_deps = False
    in_optional_deps_section = False

    for line in content.splitlines():
        stripped = line.strip()

        # Section headers
        if stripped == "[project.dependencies]" or stripped == "dependencies = [":
            in_deps = True
            in_dev_deps = False
            in_optional_deps_section = False
            continue
        if re.match(r"\[project\.optional-dependencies\]", stripped):
            in_optional_deps_section = True
            in_deps = False
            in_dev_deps = False
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            in_deps = False
            in_dev_deps = False
            in_optional_deps_section = False
            continue

        # Inside optional-dependencies section, detect group arrays like: dev = [
        if in_optional_deps_section and not in_dev_deps:
            group_match = re.match(r"(\w+)\s*=\s*\[", stripped)
            if group_match:
                group_name = group_match.group(1)
                in_dev_deps = group_name in ("dev", "test", "testing", "development")
                in_deps = not in_dev_deps  # non-dev optional deps still captured
                continue

        if in_deps or in_dev_deps:
            # Handle inline array items: "package>=1.0",
            match = re.match(r'["\']([a-zA-Z0-9_.-]+(?:\[[a-zA-Z0-9_,.-]+\])?)\s*(.*?)["\'],?', stripped)
            if match:
                name = match.group(1)
                constraint = match.group(2).strip()
                deps.append({
                    "name": name,
                    "version_constraint": constraint or None,
                    "is_dev_dependency": in_dev_deps,
                })
            if stripped == "]":
                in_deps = False
                in_dev_deps = False

    return deps


def parse_dependency_file(file_path: str, content: str) -> list[dict]:
    """Auto-detect and parse a dependency file."""
    filename = file_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]

    if filename == "package.json":
        return parse_package_json(content)
    elif filename == "requirements.txt":
        return parse_requirements_txt(content)
    elif filename == "pyproject.toml":
        return parse_pyproject_toml(content)
    return []
