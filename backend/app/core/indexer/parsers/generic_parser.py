"""Regex-based fallback parser for unsupported languages."""

from __future__ import annotations

import re

from app.core.indexer.parsers.base import (
    CodeParser,
    ParsedCodeUnit,
    ParsedFile,
    ParsedImport,
)

# Language-specific regex patterns
PATTERNS: dict[str, dict[str, list[re.Pattern]]] = {
    "go": {
        "function": [re.compile(r"^func\s+(?:\(.*?\)\s+)?(\w+)\s*\(", re.MULTILINE)],
        "class": [re.compile(r"^type\s+(\w+)\s+struct\s*\{", re.MULTILINE)],
        "interface": [re.compile(r"^type\s+(\w+)\s+interface\s*\{", re.MULTILINE)],
        "import": [re.compile(r'^import\s+(?:\(\s*([\s\S]*?)\s*\)|"(.+?)")', re.MULTILINE)],
    },
    "java": {
        "function": [re.compile(r"(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\(", re.MULTILINE)],
        "class": [re.compile(r"(?:public\s+)?(?:abstract\s+)?class\s+(\w+)", re.MULTILINE)],
        "interface": [re.compile(r"(?:public\s+)?interface\s+(\w+)", re.MULTILINE)],
        "import": [re.compile(r"^import\s+([\w.]+\*?)\s*;", re.MULTILINE)],
    },
    "rust": {
        "function": [re.compile(r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)", re.MULTILINE)],
        "class": [re.compile(r"(?:pub\s+)?struct\s+(\w+)", re.MULTILINE)],
        "interface": [re.compile(r"(?:pub\s+)?trait\s+(\w+)", re.MULTILINE)],
        "import": [re.compile(r"^use\s+([\w:]+(?:::\{.*?\})?)\s*;", re.MULTILINE)],
    },
    "ruby": {
        "function": [re.compile(r"^\s*def\s+(\w+[!?]?)", re.MULTILINE)],
        "class": [re.compile(r"^\s*class\s+(\w+)", re.MULTILINE)],
        "interface": [],
        "import": [re.compile(r"^require(?:_relative)?\s+['\"](.+?)['\"]", re.MULTILINE)],
    },
    "csharp": {
        "function": [re.compile(r"(?:public|private|protected|internal|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\(", re.MULTILINE)],
        "class": [re.compile(r"(?:public\s+)?(?:abstract\s+)?(?:partial\s+)?class\s+(\w+)", re.MULTILINE)],
        "interface": [re.compile(r"(?:public\s+)?interface\s+(I\w+)", re.MULTILINE)],
        "import": [re.compile(r"^using\s+([\w.]+)\s*;", re.MULTILINE)],
    },
}

EXT_TO_LANG: dict[str, str] = {
    ".go": "go",
    ".java": "java",
    ".rs": "rust",
    ".rb": "ruby",
    ".cs": "csharp",
}


def _find_block_end(lines: list[str], start_idx: int) -> int:
    """Find the approximate end of a code block by tracking brace depth or indentation."""
    if start_idx >= len(lines):
        return start_idx
    # Try brace counting
    depth = 0
    found_open = False
    for i in range(start_idx, min(start_idx + 500, len(lines))):
        for ch in lines[i]:
            if ch == "{":
                depth += 1
                found_open = True
            elif ch == "}":
                depth -= 1
                if found_open and depth <= 0:
                    return i
    return min(start_idx + 20, len(lines) - 1)


class GenericParser(CodeParser):
    """Regex-based fallback parser for Go, Java, Rust, Ruby, C#."""

    def supported_extensions(self) -> list[str]:
        return list(EXT_TO_LANG.keys())

    def parse(self, file_path: str, content: str) -> ParsedFile:
        ext = "." + file_path.rsplit(".", 1)[-1] if "." in file_path else ""
        lang = EXT_TO_LANG.get(ext, "")
        patterns = PATTERNS.get(lang, {})
        lines = content.split("\n")

        imports: list[ParsedImport] = []
        code_units: list[ParsedCodeUnit] = []

        # Extract imports
        for pattern in patterns.get("import", []):
            for match in pattern.finditer(content):
                source = match.group(1) if match.group(1) else (match.group(2) if match.lastindex and match.lastindex >= 2 else "")
                if source:
                    # Go multi-import block
                    if "\n" in source:
                        for line in source.strip().split("\n"):
                            line = line.strip().strip('"')
                            if line:
                                imports.append(ParsedImport(source=line, imported_names=[line.split("/")[-1]]))
                    else:
                        imports.append(ParsedImport(source=source.strip('"'), imported_names=[source.split(".")[-1].split("/")[-1]]))

        # Extract functions
        for pattern in patterns.get("function", []):
            for match in pattern.finditer(content):
                name = match.group(1)
                line_num = content[: match.start()].count("\n") + 1
                end_line = _find_block_end(lines, line_num - 1) + 1
                is_exported = lang in ("go", "rust") and name[0].isupper() if name else False
                code_units.append(
                    ParsedCodeUnit(
                        type="function",
                        name=name,
                        line_start=line_num,
                        line_end=end_line,
                        is_exported=is_exported or "public" in (match.group(0) if match.group(0) else ""),
                        body_text="\n".join(lines[line_num - 1 : end_line]),
                    )
                )

        # Extract classes/structs
        for pattern in patterns.get("class", []):
            for match in pattern.finditer(content):
                name = match.group(1)
                line_num = content[: match.start()].count("\n") + 1
                end_line = _find_block_end(lines, line_num - 1) + 1
                code_units.append(
                    ParsedCodeUnit(
                        type="class",
                        name=name,
                        line_start=line_num,
                        line_end=end_line,
                        is_exported=lang in ("go", "rust") and name[0].isupper() if name else False,
                        body_text="\n".join(lines[line_num - 1 : end_line]),
                    )
                )

        # Extract interfaces/traits
        for pattern in patterns.get("interface", []):
            for match in pattern.finditer(content):
                name = match.group(1)
                line_num = content[: match.start()].count("\n") + 1
                end_line = _find_block_end(lines, line_num - 1) + 1
                code_units.append(
                    ParsedCodeUnit(
                        type="interface",
                        name=name,
                        line_start=line_num,
                        line_end=end_line,
                        body_text="\n".join(lines[line_num - 1 : end_line]),
                    )
                )

        return ParsedFile(
            path=file_path,
            language=lang or "unknown",
            imports=imports,
            code_units=code_units,
            lines_of_code=len(lines),
        )
