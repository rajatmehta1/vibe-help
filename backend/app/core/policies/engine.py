"""Policy evaluation engine — rule-based code analysis with caching."""

from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("forgeline.engine")


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ViolationResult:
    rule_id: str
    policy_name: str
    category: str
    severity: str
    message: str
    suggestion: str | None = None
    line_start: int = 1
    line_end: int = 1
    column_start: int = 1
    column_end: int = 1
    code_snippet: str | None = None
    context_evidence: dict[str, Any] | None = None


@dataclass
class AnalysisResult:
    violations: list[ViolationResult] = field(default_factory=list)
    elapsed_ms: float = 0.0
    cached: bool = False


# ---------------------------------------------------------------------------
# In-memory cache with TTL
# ---------------------------------------------------------------------------

class AnalysisCache:
    """Simple in-memory analysis cache keyed by hash(code + file_path)."""

    def __init__(self, ttl_seconds: int = 300):
        self._cache: dict[str, tuple[float, AnalysisResult]] = {}
        self._ttl = ttl_seconds

    def _key(self, code: str, file_path: str) -> str:
        return hashlib.sha256(f"{file_path}:{code}".encode()).hexdigest()

    def get(self, code: str, file_path: str) -> AnalysisResult | None:
        key = self._key(code, file_path)
        entry = self._cache.get(key)
        if entry is None:
            return None
        ts, result = entry
        if time.time() - ts > self._ttl:
            del self._cache[key]
            return None
        cached_result = AnalysisResult(
            violations=result.violations,
            elapsed_ms=result.elapsed_ms,
            cached=True,
        )
        return cached_result

    def set(self, code: str, file_path: str, result: AnalysisResult) -> None:
        key = self._key(code, file_path)
        self._cache[key] = (time.time(), result)

    def clear(self) -> None:
        self._cache.clear()


# Singleton cache
_cache = AnalysisCache(ttl_seconds=300)


def get_cache() -> AnalysisCache:
    return _cache


# ---------------------------------------------------------------------------
# Rule-based checks (static rules)
# ---------------------------------------------------------------------------

def _find_pattern_lines(code: str, pattern: str) -> list[tuple[int, str]]:
    """Find all lines matching a regex pattern, returning (line_number, line_text)."""
    matches = []
    for i, line in enumerate(code.splitlines(), start=1):
        if re.search(pattern, line):
            matches.append((i, line.strip()))
    return matches


def check_hardcoded_secrets(code: str, file_path: str) -> list[ViolationResult]:
    """SEC-003: Detect hardcoded API keys, passwords, tokens."""
    patterns = [
        (r'["\']sk-[a-zA-Z0-9]{20,}["\']', "Hardcoded API key detected"),
        (r'["\']ghp_[a-zA-Z0-9]{20,}["\']', "Hardcoded GitHub token detected"),
        (r'(?i)password\s*=\s*["\'][^"\']+["\']', "Hardcoded password detected"),
        (r'(?i)secret\s*=\s*["\'][^"\']+["\']', "Hardcoded secret detected"),
        (r'(?i)api_key\s*=\s*["\'][^"\']+["\']', "Hardcoded API key detected"),
        (r'(?i)token\s*=\s*["\'][a-zA-Z0-9+/=]{20,}["\']', "Hardcoded token detected"),
    ]
    violations = []
    for pat, msg in patterns:
        for line_no, line_text in _find_pattern_lines(code, pat):
            violations.append(ViolationResult(
                rule_id="SEC-003",
                policy_name="OWASP Security Basics",
                category="security",
                severity="error",
                message=msg,
                suggestion="Use environment variables or a secrets manager instead of hardcoding credentials.",
                line_start=line_no,
                line_end=line_no,
                code_snippet=line_text,
            ))
    return violations


def check_naming_conventions(code: str, file_path: str, language: str) -> list[ViolationResult]:
    """NAM-001/002: Detect naming convention violations."""
    violations = []
    lines = code.splitlines()

    # Detect function definitions with wrong casing
    if language in ("python",):
        # Python expects snake_case
        for i, line in enumerate(lines, 1):
            m = re.match(r'\s*def\s+([a-zA-Z_]\w*)\s*\(', line)
            if m:
                name = m.group(1)
                if name.startswith("_"):
                    continue
                # Check if camelCase (has lowercase followed by uppercase)
                if re.search(r'[a-z][A-Z]', name):
                    violations.append(ViolationResult(
                        rule_id="NAM-001",
                        policy_name="Naming Conventions",
                        category="naming",
                        severity="warning",
                        message=f"Function '{name}' uses camelCase. Python convention is snake_case.",
                        suggestion=f"Rename to '{_to_snake_case(name)}'.",
                        line_start=i,
                        line_end=i,
                        code_snippet=line.strip(),
                    ))
    elif language in ("typescript", "javascript"):
        # JS/TS expects camelCase for functions
        for i, line in enumerate(lines, 1):
            m = re.match(r'\s*(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z_]\w*)\s*[(<]', line)
            if not m:
                m = re.match(r'\s*(?:export\s+)?(?:const|let)\s+([a-zA-Z_]\w*)\s*=\s*(?:async\s*)?\(', line)
            if m:
                name = m.group(1)
                # Check for snake_case (has underscores)
                if '_' in name and not name.startswith('_') and not name.isupper():
                    violations.append(ViolationResult(
                        rule_id="NAM-001",
                        policy_name="Naming Conventions",
                        category="naming",
                        severity="warning",
                        message=f"Function '{name}' uses snake_case. TypeScript/JavaScript convention is camelCase.",
                        suggestion=f"Rename to '{_to_camel_case(name)}'.",
                        line_start=i,
                        line_end=i,
                        code_snippet=line.strip(),
                    ))

    # Vague function names
    vague_names = {"getData", "get_data", "doStuff", "do_stuff", "process", "handle", "run", "execute"}
    for i, line in enumerate(lines, 1):
        m = re.match(r'\s*(?:def|function|const|let|var|export)\s+(?:async\s+)?(?:function\s+)?([a-zA-Z_]\w*)', line)
        if m and m.group(1) in vague_names:
            violations.append(ViolationResult(
                rule_id="NAM-003",
                policy_name="Naming Conventions",
                category="naming",
                severity="warning",
                message=f"Function '{m.group(1)}' has a vague name that doesn't describe its purpose.",
                suggestion="Use a more descriptive name like 'fetchUsersByStatus' or 'processPaymentBatch'.",
                line_start=i,
                line_end=i,
                code_snippet=line.strip(),
            ))

    return violations


def check_error_handling(code: str, file_path: str, language: str) -> list[ViolationResult]:
    """ERR-001/004: Detect bad error handling patterns."""
    violations = []
    lines = code.splitlines()

    if language in ("python",):
        # Bare except
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped == "except:" or stripped == "except :":
                violations.append(ViolationResult(
                    rule_id="ERR-001",
                    policy_name="Error Handling Consistency",
                    category="error_handling",
                    severity="warning",
                    message="Bare 'except:' clause catches all exceptions including SystemExit and KeyboardInterrupt.",
                    suggestion="Catch a specific exception type, e.g., 'except Exception as e:'.",
                    line_start=i,
                    line_end=i,
                    code_snippet=stripped,
                ))
    elif language in ("typescript", "javascript"):
        # Empty catch blocks
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if re.match(r'}\s*catch\s*\([^)]*\)\s*\{\s*\}', stripped):
                violations.append(ViolationResult(
                    rule_id="ERR-004",
                    policy_name="Error Handling Consistency",
                    category="error_handling",
                    severity="warning",
                    message="Empty catch block silently swallows errors.",
                    suggestion="At minimum, log the error or re-throw it.",
                    line_start=i,
                    line_end=i,
                    code_snippet=stripped,
                ))

        # Check for swallowed exceptions (catch with only comment or pass)
        for i in range(len(lines)):
            stripped = lines[i].strip()
            catch_match = re.match(r'}\s*catch\s*\(', stripped)
            if catch_match and i + 1 < len(lines):
                next_stripped = lines[i + 1].strip()
                if next_stripped == "}" or next_stripped.startswith("//"):
                    violations.append(ViolationResult(
                        rule_id="ERR-004",
                        policy_name="Error Handling Consistency",
                        category="error_handling",
                        severity="warning",
                        message="Catch block appears to swallow the exception without handling it.",
                        suggestion="Log the error, show a user message, or re-throw.",
                        line_start=i + 1,
                        line_end=i + 2,
                        code_snippet=stripped,
                    ))

    return violations


def check_architecture_violations(code: str, file_path: str) -> list[ViolationResult]:
    """ARC-002: Detect architecture layer boundary violations."""
    violations = []

    # Controller importing from repository (skipping service layer)
    if "/controllers/" in file_path or "\\controllers\\" in file_path:
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            if re.search(r'(?:import|from|require).*(?:repository|repositories|repo)', line, re.IGNORECASE):
                violations.append(ViolationResult(
                    rule_id="ARC-002",
                    policy_name="Layered Architecture",
                    category="architecture",
                    severity="warning",
                    message="Controller directly imports from repository layer, bypassing the service layer.",
                    suggestion="Controllers should only depend on services. Move data access logic to a service.",
                    line_start=i,
                    line_end=i,
                    code_snippet=line.strip(),
                ))

    return violations


# ---------------------------------------------------------------------------
# Main evaluation entry point
# ---------------------------------------------------------------------------

def evaluate_code(
    code: str,
    file_path: str,
    language: str,
    policies: list[dict[str, Any]],
) -> AnalysisResult:
    """Evaluate a code snippet against active policies.

    Args:
        code: The source code to analyze.
        file_path: Path of the file being analyzed.
        language: Programming language (python, typescript, javascript, etc.).
        policies: List of active policy dicts with 'category', 'severity_default',
                  'is_active', and 'configuration'.

    Returns:
        AnalysisResult with list of violations found.
    """
    # Check cache first
    cached = _cache.get(code, file_path)
    if cached is not None:
        logger.info("Cache hit for %s", file_path)
        return cached

    start = time.perf_counter()
    all_violations: list[ViolationResult] = []

    # Build a set of active categories
    active_categories = set()
    severity_map: dict[str, str] = {}
    for pol in policies:
        if pol.get("is_active", True):
            cat = pol.get("category", "")
            active_categories.add(cat)
            severity_map[cat] = pol.get("severity_default", "warning")

    # Run checks based on active policy categories
    if "security" in active_categories:
        results = check_hardcoded_secrets(code, file_path)
        for v in results:
            v.severity = severity_map.get("security", v.severity)
        all_violations.extend(results)
        _log_timing("security checks", start)

    if "naming" in active_categories:
        results = check_naming_conventions(code, file_path, language)
        for v in results:
            v.severity = severity_map.get("naming", v.severity)
        all_violations.extend(results)
        _log_timing("naming checks", start)

    if "error_handling" in active_categories:
        results = check_error_handling(code, file_path, language)
        for v in results:
            v.severity = severity_map.get("error_handling", v.severity)
        all_violations.extend(results)
        _log_timing("error handling checks", start)

    if "architecture" in active_categories:
        results = check_architecture_violations(code, file_path)
        for v in results:
            v.severity = severity_map.get("architecture", v.severity)
        all_violations.extend(results)
        _log_timing("architecture checks", start)

    elapsed = (time.perf_counter() - start) * 1000

    if elapsed > 500:
        logger.warning("Analysis took %.1fms for %s (exceeds 500ms threshold)", elapsed, file_path)
    else:
        logger.info("Analysis completed in %.1fms for %s — %d violations", elapsed, file_path, len(all_violations))

    result = AnalysisResult(violations=all_violations, elapsed_ms=elapsed)
    _cache.set(code, file_path, result)
    return result


def _log_timing(check_name: str, start: float) -> None:
    elapsed = (time.perf_counter() - start) * 1000
    logger.debug("  %s: %.1fms", check_name, elapsed)


def _to_snake_case(name: str) -> str:
    s = re.sub(r'([A-Z])', r'_\1', name).lower().lstrip('_')
    return re.sub(r'_+', '_', s)


def _to_camel_case(name: str) -> str:
    parts = name.split('_')
    return parts[0] + ''.join(p.capitalize() for p in parts[1:])
