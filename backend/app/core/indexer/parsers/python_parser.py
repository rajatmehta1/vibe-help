"""Python source code parser using tree-sitter."""

from __future__ import annotations

import tree_sitter_python as tsp
from tree_sitter import Language, Node, Parser

from app.core.indexer.parsers.base import (
    CodeParser,
    ParsedCodeUnit,
    ParsedFile,
    ParsedImport,
)

PY_LANGUAGE = Language(tsp.language())

COMPLEXITY_NODE_TYPES = frozenset(
    {
        "if_statement",
        "elif_clause",
        "for_statement",
        "while_statement",
        "except_clause",
        "with_statement",
        "conditional_expression",  # ternary
        "boolean_operator",  # and / or
        "list_comprehension",
        "set_comprehension",
        "dictionary_comprehension",
        "generator_expression",
    }
)


def _text(node: Node) -> str:
    return node.text.decode("utf-8") if node.text else ""


def _complexity(node: Node) -> int:
    count = 1  # base
    for child in _walk(node):
        if child.type in COMPLEXITY_NODE_TYPES:
            count += 1
    return count


def _walk(node: Node):
    """Yield all descendants of a node."""
    for child in node.children:
        yield child
        yield from _walk(child)


def _extract_docstring(node: Node) -> str | None:
    """Extract docstring from the first expression_statement child if it's a string."""
    body = node.child_by_field_name("body")
    if body is None:
        return None
    for child in body.children:
        if child.type == "expression_statement" and child.children:
            expr = child.children[0]
            if expr.type == "string":
                raw = _text(expr)
                # Strip triple quotes
                for q in ('"""', "'''"):
                    if raw.startswith(q) and raw.endswith(q):
                        return raw[3:-3].strip()
                return raw.strip("\"'").strip()
        elif child.type != "comment":
            break
    return None


def _extract_decorators(node: Node) -> list[str]:
    decorators = []
    for child in node.children:
        if child.type == "decorator":
            decorators.append(_text(child).lstrip("@").strip())
    return decorators


def _extract_params(node: Node) -> list[dict]:
    params_node = node.child_by_field_name("parameters")
    if params_node is None:
        return []
    params = []
    for child in params_node.children:
        if child.type in ("identifier", "typed_parameter", "default_parameter",
                          "typed_default_parameter", "list_splat_pattern",
                          "dictionary_splat_pattern"):
            param: dict = {"name": "", "type": None, "default": None}
            if child.type == "identifier":
                param["name"] = _text(child)
            elif child.type == "typed_parameter":
                name_node = child.children[0] if child.children else None
                param["name"] = _text(name_node) if name_node else ""
                type_node = child.child_by_field_name("type")
                if type_node:
                    param["type"] = _text(type_node)
            elif child.type == "default_parameter":
                name_node = child.child_by_field_name("name")
                value_node = child.child_by_field_name("value")
                param["name"] = _text(name_node) if name_node else ""
                param["default"] = _text(value_node) if value_node else None
            elif child.type == "typed_default_parameter":
                name_node = child.child_by_field_name("name")
                type_node = child.child_by_field_name("type")
                value_node = child.child_by_field_name("value")
                param["name"] = _text(name_node) if name_node else ""
                param["type"] = _text(type_node) if type_node else None
                param["default"] = _text(value_node) if value_node else None
            elif child.type == "list_splat_pattern":
                name = ""
                for sub in child.children:
                    if sub.type == "identifier":
                        name = _text(sub)
                        break
                param["name"] = "*" + name
            elif child.type == "dictionary_splat_pattern":
                name = ""
                for sub in child.children:
                    if sub.type == "identifier":
                        name = _text(sub)
                        break
                param["name"] = "**" + name
            if param["name"] and param["name"] != "self" and param["name"] != "cls":
                params.append(param)
    return params


def _extract_return_type(node: Node) -> str | None:
    ret = node.child_by_field_name("return_type")
    if ret:
        return _text(ret)
    return None


def _parse_function(node: Node, is_top_level: bool = True) -> ParsedCodeUnit:
    name_node = node.child_by_field_name("name")
    name = _text(name_node) if name_node else "<anonymous>"
    is_async = node.type == "function_definition" and any(
        c.type == "async" for c in (node.parent.children if node.parent else [])
    )
    # Check if parent is actually decorated_definition with async
    if node.parent and node.parent.type == "decorated_definition":
        # async might be before the def in grandparent
        pass

    # Simpler async check: look at the full text
    body = _text(node)
    is_async = body.lstrip().startswith("async ")

    return ParsedCodeUnit(
        type="function",
        name=name,
        line_start=node.start_point[0] + 1,
        line_end=node.end_point[0] + 1,
        params=_extract_params(node),
        return_type=_extract_return_type(node),
        is_async=is_async,
        is_exported=is_top_level and not name.startswith("_"),
        docstring=_extract_docstring(node),
        body_text=_text(node),
        decorators=_extract_decorators(node.parent) if node.parent and node.parent.type == "decorated_definition" else [],
        complexity=_complexity(node),
    )


def _parse_class(node: Node, is_top_level: bool = True) -> ParsedCodeUnit:
    name_node = node.child_by_field_name("name")
    name = _text(name_node) if name_node else "<anonymous>"

    # Extract base classes
    bases = []
    superclasses = node.child_by_field_name("superclasses")
    if superclasses:
        for child in superclasses.children:
            if child.type not in ("(", ")", ","):
                bases.append(_text(child))

    # Extract methods as children
    children = []
    body = node.child_by_field_name("body")
    if body:
        for child in body.children:
            actual = child
            if child.type == "decorated_definition":
                for sub in child.children:
                    if sub.type == "function_definition":
                        actual = sub
                        break
            if actual.type == "function_definition":
                fn = _parse_function(actual, is_top_level=False)
                fn.decorators = _extract_decorators(child) if child.type == "decorated_definition" else []
                children.append(fn)

    return ParsedCodeUnit(
        type="class",
        name=name,
        line_start=node.start_point[0] + 1,
        line_end=node.end_point[0] + 1,
        is_exported=is_top_level and not name.startswith("_"),
        docstring=_extract_docstring(node),
        body_text=_text(node),
        children=children,
        base_classes=bases,
        decorators=_extract_decorators(node.parent) if node.parent and node.parent.type == "decorated_definition" else [],
        complexity=_complexity(node),
    )


def _parse_import(node: Node) -> list[ParsedImport]:
    results: list[ParsedImport] = []

    if node.type == "import_statement":
        # import foo, import foo.bar
        for child in node.children:
            if child.type == "dotted_name":
                results.append(ParsedImport(source=_text(child), imported_names=[_text(child).split(".")[-1]]))
            elif child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                alias_node = child.child_by_field_name("alias")
                source = _text(name_node) if name_node else ""
                results.append(ParsedImport(
                    source=source,
                    imported_names=[source.split(".")[-1]],
                    alias=_text(alias_node) if alias_node else None,
                ))

    elif node.type == "import_from_statement":
        # from foo import bar, baz
        module_name = node.child_by_field_name("module_name")
        source = _text(module_name) if module_name else ""

        # Check for relative imports (leading dots)
        is_relative = False
        for child in node.children:
            if child.type == "relative_import":
                source = _text(child)
                is_relative = True
                break
            if child.type == "." or child.type == "...":
                is_relative = True

        if not source:
            # Build from dots + module
            parts = []
            for child in node.children:
                if _text(child) == ".":
                    parts.append(".")
                elif child.type == "dotted_name":
                    parts.append(_text(child))
                    break
            source = "".join(parts)
            if parts and parts[0] == ".":
                is_relative = True

        names: list[str] = []
        for child in node.children:
            if child.type == "dotted_name" and child != module_name:
                names.append(_text(child))
            elif child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                if name_node:
                    names.append(_text(name_node))
            elif child.type == "wildcard_import":
                names.append("*")

        if names:
            results.append(ParsedImport(source=source, imported_names=names, is_relative=is_relative))

    return results


def _parse_variable(node: Node) -> dict | None:
    """Parse a top-level assignment or annotated assignment."""
    if node.type == "expression_statement" and node.children:
        expr = node.children[0]
        if expr.type == "assignment":
            left = expr.child_by_field_name("left")
            right = expr.child_by_field_name("right")
            if left and left.type == "identifier":
                name = _text(left)
                value = _text(right) if right else None
                return {
                    "name": name,
                    "type_annotation": None,
                    "is_constant": name.isupper(),
                    "value_preview": (value[:80] + "...") if value and len(value) > 80 else value,
                }
    elif node.type == "expression_statement" and node.children:
        expr = node.children[0]
        if expr.type == "type_alias_statement":
            pass  # type aliases handled elsewhere

    if node.type == "type_alias_statement":
        name_node = node.child_by_field_name("name")
        if name_node:
            return {
                "name": _text(name_node),
                "type_annotation": "TypeAlias",
                "is_constant": False,
                "value_preview": _text(node),
            }

    return None


class PythonParser(CodeParser):
    """Python parser using tree-sitter."""

    def __init__(self) -> None:
        self._parser = Parser(PY_LANGUAGE)

    def supported_extensions(self) -> list[str]:
        return [".py"]

    def parse(self, file_path: str, content: str) -> ParsedFile:
        tree = self._parser.parse(content.encode("utf-8"))
        root = tree.root_node

        imports: list[ParsedImport] = []
        code_units: list[ParsedCodeUnit] = []
        variables: list[dict] = []

        for child in root.children:
            actual = child
            if child.type == "decorated_definition":
                for sub in child.children:
                    if sub.type in ("function_definition", "class_definition"):
                        actual = sub
                        break

            if actual.type == "function_definition":
                fn = _parse_function(actual, is_top_level=True)
                fn.decorators = _extract_decorators(child) if child.type == "decorated_definition" else []
                code_units.append(fn)
            elif actual.type == "class_definition":
                cls = _parse_class(actual, is_top_level=True)
                cls.decorators = _extract_decorators(child) if child.type == "decorated_definition" else []
                code_units.append(cls)
            elif child.type in ("import_statement", "import_from_statement"):
                imports.extend(_parse_import(child))
            else:
                var = _parse_variable(child)
                if var:
                    variables.append(var)

        return ParsedFile(
            path=file_path,
            language="python",
            imports=imports,
            code_units=code_units,
            top_level_variables=variables,
            lines_of_code=content.count("\n") + (1 if content and not content.endswith("\n") else 0),
        )
