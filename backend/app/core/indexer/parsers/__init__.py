"""Parser registry — maps file extensions to parser instances."""

from __future__ import annotations

from app.core.indexer.parsers.base import CodeParser, ParsedCodeUnit, ParsedFile, ParsedImport
from app.core.indexer.parsers.generic_parser import GenericParser
from app.core.indexer.parsers.python_parser import PythonParser
from app.core.indexer.parsers.typescript_parser import TypeScriptParser


class ParserRegistry:
    """Maps file extensions to CodeParser instances."""

    def __init__(self) -> None:
        self._parsers: dict[str, CodeParser] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        for parser in (PythonParser(), TypeScriptParser(), GenericParser()):
            for ext in parser.supported_extensions():
                self._parsers[ext] = parser

    def register(self, parser: CodeParser) -> None:
        for ext in parser.supported_extensions():
            self._parsers[ext] = parser

    def get_parser(self, file_path: str) -> CodeParser | None:
        ext = ""
        if "." in file_path:
            ext = "." + file_path.rsplit(".", 1)[-1]
        return self._parsers.get(ext)

    def supported_extensions(self) -> list[str]:
        return sorted(self._parsers.keys())


__all__ = [
    "CodeParser",
    "GenericParser",
    "ParsedCodeUnit",
    "ParsedFile",
    "ParsedImport",
    "ParserRegistry",
    "PythonParser",
    "TypeScriptParser",
]
