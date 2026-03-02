"""Base classes for code parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ParsedCodeUnit:
    """Represents a parsed code element."""

    type: str  # "function", "class", "module", "interface", "variable"
    name: str
    line_start: int
    line_end: int
    params: list[dict] | None = None  # [{name, type, default}]
    return_type: str | None = None
    is_async: bool = False
    is_exported: bool = False
    docstring: str | None = None
    body_text: str = ""
    children: list[ParsedCodeUnit] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    base_classes: list[str] = field(default_factory=list)
    implements: list[str] = field(default_factory=list)
    complexity: int = 1


@dataclass
class ParsedImport:
    """Represents an import statement."""

    source: str  # Module/file path
    imported_names: list[str] = field(default_factory=list)  # ["funcA", "ClassB"] or ["*"]
    is_relative: bool = False
    alias: str | None = None


@dataclass
class ParsedFile:
    """Represents a fully parsed source file."""

    path: str
    language: str
    imports: list[ParsedImport] = field(default_factory=list)
    code_units: list[ParsedCodeUnit] = field(default_factory=list)
    top_level_variables: list[dict] = field(default_factory=list)
    lines_of_code: int = 0
    package_dependencies: list[dict] = field(default_factory=list)


class CodeParser(ABC):
    """Abstract base class for language-specific code parsers."""

    @abstractmethod
    def parse(self, file_path: str, content: str) -> ParsedFile:
        """Parse a source file and return its structure."""

    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return list of file extensions this parser handles (e.g. ['.py'])."""
