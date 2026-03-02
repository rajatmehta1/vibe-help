"""Tests for the code parsers."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.core.indexer.parsers import ParserRegistry
from app.core.indexer.parsers.base import ParsedFile, ParsedCodeUnit, ParsedImport
from app.core.indexer.parsers.python_parser import PythonParser
from app.core.indexer.parsers.typescript_parser import TypeScriptParser
from app.core.indexer.parsers.generic_parser import GenericParser
from app.core.indexer.parsers.dependency_parser import (
    parse_dependency_file,
    parse_package_json,
    parse_requirements_txt,
    parse_pyproject_toml,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# ParserRegistry
# ---------------------------------------------------------------------------
class TestParserRegistry:
    def test_python_extension(self):
        registry = ParserRegistry()
        parser = registry.get_parser("main.py")
        assert parser is not None
        assert isinstance(parser, PythonParser)

    def test_typescript_extensions(self):
        registry = ParserRegistry()
        for ext in (".ts", ".tsx", ".js", ".jsx"):
            parser = registry.get_parser(f"file{ext}")
            assert parser is not None, f"No parser for {ext}"
            assert isinstance(parser, TypeScriptParser)

    def test_generic_extensions(self):
        registry = ParserRegistry()
        for ext in (".go", ".java", ".rs", ".rb", ".cs"):
            parser = registry.get_parser(f"file{ext}")
            assert parser is not None, f"No parser for {ext}"
            assert isinstance(parser, GenericParser)

    def test_unknown_extension_returns_none(self):
        registry = ParserRegistry()
        assert registry.get_parser("file.xyz") is None

    def test_supported_extensions_sorted(self):
        registry = ParserRegistry()
        exts = registry.supported_extensions()
        assert exts == sorted(exts)
        assert ".py" in exts
        assert ".ts" in exts
        assert ".go" in exts


# ---------------------------------------------------------------------------
# PythonParser
# ---------------------------------------------------------------------------
class TestPythonParser:
    @pytest.fixture()
    def parsed(self) -> ParsedFile:
        parser = PythonParser()
        content = _read_fixture("sample_python.py")
        return parser.parse("sample_python.py", content)

    def test_language(self, parsed: ParsedFile):
        assert parsed.language == "python"

    def test_lines_of_code(self, parsed: ParsedFile):
        assert parsed.lines_of_code > 50

    # -- imports --
    def test_import_count(self, parsed: ParsedFile):
        assert len(parsed.imports) >= 6

    def test_stdlib_imports(self, parsed: ParsedFile):
        sources = [i.source for i in parsed.imports]
        assert "os" in sources
        assert "sys" in sources

    def test_relative_imports(self, parsed: ParsedFile):
        relative = [i for i in parsed.imports if i.is_relative]
        assert len(relative) >= 2
        names_flat = [n for i in relative for n in i.imported_names]
        assert "helper_function" in names_flat
        assert "User" in names_flat or "Organization" in names_flat

    def test_from_import_names(self, parsed: ParsedFile):
        pathlib_imp = next((i for i in parsed.imports if i.source == "pathlib"), None)
        assert pathlib_imp is not None
        assert "Path" in pathlib_imp.imported_names

    # -- functions --
    def test_simple_function(self, parsed: ParsedFile):
        fn = _find_unit(parsed, "function", "simple_function")
        assert fn is not None
        assert fn.return_type is not None
        assert fn.docstring is not None
        assert fn.is_exported is True  # top-level, doesn't start with _
        assert fn.params is not None
        assert len(fn.params) == 2

    def test_async_function(self, parsed: ParsedFile):
        fn = _find_unit(parsed, "function", "fetch_data")
        assert fn is not None
        assert fn.is_async is True
        assert fn.docstring is not None

    def test_private_function(self, parsed: ParsedFile):
        fn = _find_unit(parsed, "function", "_private_helper")
        assert fn is not None
        assert fn.is_exported is False

    def test_complex_function_params(self, parsed: ParsedFile):
        fn = _find_unit(parsed, "function", "complex_function")
        assert fn is not None
        assert fn.params is not None
        param_names = [p["name"] for p in fn.params]
        assert "data" in param_names
        assert "**kwargs" in param_names

    def test_complexity_higher_for_branches(self, parsed: ParsedFile):
        simple = _find_unit(parsed, "function", "simple_function")
        complex_fn = _find_unit(parsed, "function", "complex_function")
        assert simple is not None and complex_fn is not None
        assert complex_fn.complexity > simple.complexity

    # -- classes --
    def test_base_class(self, parsed: ParsedFile):
        cls = _find_unit(parsed, "class", "BaseProcessor")
        assert cls is not None
        assert cls.docstring is not None
        assert cls.is_exported is True
        methods = [c.name for c in cls.children]
        assert "__init__" in methods
        assert "process" in methods

    def test_derived_class(self, parsed: ParsedFile):
        cls = _find_unit(parsed, "class", "DataProcessor")
        assert cls is not None
        assert "BaseProcessor" in cls.base_classes
        methods = [c.name for c in cls.children]
        assert "process" in methods
        assert "_validate" in methods

    def test_async_class_methods(self, parsed: ParsedFile):
        cls = _find_unit(parsed, "class", "AsyncWorker")
        assert cls is not None
        run_method = next((c for c in cls.children if c.name == "run"), None)
        assert run_method is not None
        assert run_method.is_async is True

    # -- variables --
    def test_top_level_variables(self, parsed: ParsedFile):
        var_names = [v["name"] for v in parsed.top_level_variables]
        assert "MAX_RETRIES" in var_names
        assert "DEFAULT_TIMEOUT" in var_names

    def test_constant_detection(self, parsed: ParsedFile):
        max_r = next((v for v in parsed.top_level_variables if v["name"] == "MAX_RETRIES"), None)
        assert max_r is not None
        assert max_r["is_constant"] is True


# ---------------------------------------------------------------------------
# TypeScriptParser
# ---------------------------------------------------------------------------
class TestTypeScriptParser:
    @pytest.fixture()
    def parsed(self) -> ParsedFile:
        parser = TypeScriptParser()
        content = _read_fixture("sample_typescript.ts")
        return parser.parse("sample_typescript.ts", content)

    def test_language(self, parsed: ParsedFile):
        assert parsed.language == "typescript"

    def test_lines_of_code(self, parsed: ParsedFile):
        assert parsed.lines_of_code > 50

    # -- imports --
    def test_import_count(self, parsed: ParsedFile):
        assert len(parsed.imports) >= 4

    def test_named_imports(self, parsed: ParsedFile):
        express_imp = next((i for i in parsed.imports if i.source == "express"), None)
        assert express_imp is not None
        assert "Request" in express_imp.imported_names
        assert "Response" in express_imp.imported_names

    def test_namespace_import(self, parsed: ParsedFile):
        crypto_imp = next((i for i in parsed.imports if i.source == "crypto"), None)
        assert crypto_imp is not None
        names = crypto_imp.imported_names
        assert any("crypto" in n for n in names)

    def test_relative_imports(self, parsed: ParsedFile):
        relative = [i for i in parsed.imports if i.is_relative]
        assert len(relative) >= 2
        sources = [i.source for i in relative]
        assert any("user-service" in s for s in sources)

    # -- functions --
    def test_exported_function(self, parsed: ParsedFile):
        fn = _find_unit(parsed, "function", "generateId")
        assert fn is not None
        assert fn.is_exported is True
        assert fn.docstring is not None

    def test_async_function(self, parsed: ParsedFile):
        fn = _find_unit(parsed, "function", "fetchWithRetry")
        assert fn is not None
        assert fn.is_async is True
        assert fn.is_exported is True
        assert fn.params is not None
        assert len(fn.params) >= 2

    def test_private_function(self, parsed: ParsedFile):
        fn = _find_unit(parsed, "function", "_internalHelper")
        assert fn is not None
        assert fn.is_exported is False

    def test_arrow_function_exported(self, parsed: ParsedFile):
        fn = _find_unit(parsed, "function", "processItems")
        assert fn is not None
        assert fn.is_exported is True
        assert fn.is_async is True

    def test_arrow_middleware(self, parsed: ParsedFile):
        fn = _find_unit(parsed, "function", "createMiddleware")
        assert fn is not None
        assert fn.is_exported is True

    def test_complexity_for_retry_logic(self, parsed: ParsedFile):
        fn = _find_unit(parsed, "function", "fetchWithRetry")
        simple = _find_unit(parsed, "function", "generateId")
        assert fn is not None and simple is not None
        assert fn.complexity > simple.complexity

    # -- classes --
    def test_base_handler_class(self, parsed: ParsedFile):
        cls = _find_unit(parsed, "class", "BaseHandler")
        assert cls is not None
        assert cls.is_exported is True
        assert cls.docstring is not None
        methods = [c.name for c in cls.children]
        assert "initialize" in methods
        assert "handleError" in methods

    def test_user_handler_extends(self, parsed: ParsedFile):
        cls = _find_unit(parsed, "class", "UserHandler")
        assert cls is not None
        assert "BaseHandler" in cls.base_classes
        methods = [c.name for c in cls.children]
        assert "getUser" in methods
        assert "createUser" in methods

    def test_internal_class_not_exported(self, parsed: ParsedFile):
        cls = _find_unit(parsed, "class", "InternalCache")
        assert cls is not None
        assert cls.is_exported is False

    # -- interfaces --
    def test_interface(self, parsed: ParsedFile):
        iface = _find_unit(parsed, "interface", "ApiResponse")
        assert iface is not None
        assert iface.is_exported is True
        assert iface.docstring is not None

    def test_middleware_config_interface(self, parsed: ParsedFile):
        iface = _find_unit(parsed, "interface", "MiddlewareConfig")
        assert iface is not None
        assert iface.is_exported is True

    # -- type alias --
    def test_type_alias(self, parsed: ParsedFile):
        ta = _find_unit(parsed, "interface", "UserId")
        assert ta is not None
        assert ta.is_exported is True

    # -- variables --
    def test_exported_const(self, parsed: ParsedFile):
        var_names = [v["name"] for v in parsed.top_level_variables]
        assert "MAX_RETRIES" in var_names or "DEFAULT_TIMEOUT" in var_names


# ---------------------------------------------------------------------------
# GenericParser
# ---------------------------------------------------------------------------
class TestGenericParser:
    def test_go_function(self):
        parser = GenericParser()
        code = '''package main

import "fmt"

func Hello(name string) string {
    return fmt.Sprintf("Hello, %s!", name)
}

func main() {
    fmt.Println(Hello("world"))
}
'''
        result = parser.parse("main.go", code)
        assert result.language == "go"
        fns = [u for u in result.code_units if u.type == "function"]
        names = [f.name for f in fns]
        assert "Hello" in names
        assert "main" in names
        hello = next(f for f in fns if f.name == "Hello")
        assert hello.is_exported is True  # uppercase = exported in Go

    def test_go_struct(self):
        parser = GenericParser()
        code = '''package main

type Config struct {
    Host string
    Port int
}
'''
        result = parser.parse("config.go", code)
        classes = [u for u in result.code_units if u.type == "class"]
        assert any(c.name == "Config" for c in classes)

    def test_go_imports(self):
        parser = GenericParser()
        code = '''package main

import (
    "fmt"
    "net/http"
    "encoding/json"
)
'''
        result = parser.parse("main.go", code)
        assert len(result.imports) >= 3
        sources = [i.source for i in result.imports]
        assert "fmt" in sources
        assert "net/http" in sources

    def test_rust_function(self):
        parser = GenericParser()
        code = '''pub fn process(data: &str) -> Result<String, Error> {
    Ok(data.to_string())
}

fn helper() {
    println!("internal");
}
'''
        result = parser.parse("lib.rs", code)
        fns = [u for u in result.code_units if u.type == "function"]
        names = [f.name for f in fns]
        assert "process" in names
        assert "helper" in names

    def test_java_class(self):
        parser = GenericParser()
        code = '''import java.util.List;

public class UserService {
    public void createUser(String name) {
        System.out.println(name);
    }

    private int calculate(int x) {
        return x * 2;
    }
}
'''
        result = parser.parse("UserService.java", code)
        assert result.language == "java"
        classes = [u for u in result.code_units if u.type == "class"]
        assert any(c.name == "UserService" for c in classes)
        fns = [u for u in result.code_units if u.type == "function"]
        fn_names = [f.name for f in fns]
        assert "createUser" in fn_names
        assert len(result.imports) >= 1

    def test_ruby_class_and_methods(self):
        parser = GenericParser()
        code = '''require 'json'
require_relative 'helpers'

class Calculator
  def add(a, b)
    a + b
  end

  def multiply(a, b)
    a * b
  end
end
'''
        result = parser.parse("calculator.rb", code)
        assert result.language == "ruby"
        assert len(result.imports) >= 2
        fns = [u for u in result.code_units if u.type == "function"]
        fn_names = [f.name for f in fns]
        assert "add" in fn_names
        assert "multiply" in fn_names

    def test_unsupported_language_returns_empty(self):
        parser = GenericParser()
        result = parser.parse("file.xyz", "some content")
        assert result.language == "unknown"
        assert len(result.code_units) == 0


# ---------------------------------------------------------------------------
# DependencyParser
# ---------------------------------------------------------------------------
class TestDependencyParser:
    def test_package_json(self):
        content = '''{
  "name": "my-app",
  "dependencies": {
    "express": "^4.18.0",
    "lodash": "~4.17.21"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "jest": "^29.0.0"
  }
}'''
        deps = parse_package_json(content)
        assert len(deps) == 4
        names = [d["name"] for d in deps]
        assert "express" in names
        assert "typescript" in names
        ts = next(d for d in deps if d["name"] == "typescript")
        assert ts["is_dev_dependency"] is True
        express = next(d for d in deps if d["name"] == "express")
        assert express["is_dev_dependency"] is False

    def test_requirements_txt(self):
        content = """fastapi>=0.100.0
sqlalchemy[asyncio]==2.0.20
# this is a comment
pydantic>=2.0

-e ./local-package
uvicorn
"""
        deps = parse_requirements_txt(content)
        names = [d["name"] for d in deps]
        assert "fastapi" in names
        assert "sqlalchemy" in names or "sqlalchemy[asyncio]" in names
        assert "uvicorn" in names
        # Comments and -e lines should be skipped
        assert not any(d["name"].startswith("#") for d in deps)
        assert not any(d["name"].startswith("-") for d in deps)

    def test_pyproject_toml(self):
        content = """[project]
name = "my-project"
dependencies = [
    "fastapi>=0.100",
    "sqlalchemy==2.0.20",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "black",
]
"""
        deps = parse_pyproject_toml(content)
        names = [d["name"] for d in deps]
        assert "fastapi" in names
        assert "sqlalchemy" in names
        assert "pytest" in names
        pytest_dep = next(d for d in deps if d["name"] == "pytest")
        assert pytest_dep["is_dev_dependency"] is True

    def test_auto_detect_package_json(self):
        content = '{"dependencies": {"react": "^18.0.0"}}'
        deps = parse_dependency_file("package.json", content)
        assert len(deps) == 1
        assert deps[0]["name"] == "react"

    def test_auto_detect_requirements_txt(self):
        deps = parse_dependency_file("requirements.txt", "flask>=2.0\nredis\n")
        names = [d["name"] for d in deps]
        assert "flask" in names
        assert "redis" in names

    def test_unsupported_file_returns_empty(self):
        deps = parse_dependency_file("Makefile", "all: build")
        assert deps == []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _find_unit(parsed: ParsedFile, unit_type: str, name: str) -> ParsedCodeUnit | None:
    for unit in parsed.code_units:
        if unit.type == unit_type and unit.name == name:
            return unit
    return None
