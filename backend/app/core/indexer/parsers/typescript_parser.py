"""TypeScript/JavaScript source code parser using tree-sitter."""

from __future__ import annotations

import tree_sitter_javascript as tsj
import tree_sitter_typescript as tst
from tree_sitter import Language, Node, Parser

from app.core.indexer.parsers.base import (
    CodeParser,
    ParsedCodeUnit,
    ParsedFile,
    ParsedImport,
)

TS_LANGUAGE = Language(tst.language_typescript())
TSX_LANGUAGE = Language(tst.language_tsx())
JS_LANGUAGE = Language(tsj.language())

COMPLEXITY_NODE_TYPES = frozenset(
    {
        "if_statement",
        "else_clause",
        "for_statement",
        "for_in_statement",
        "while_statement",
        "do_statement",
        "switch_case",
        "catch_clause",
        "ternary_expression",
        "binary_expression",  # checked for && and ||
    }
)


def _text(node: Node) -> str:
    return node.text.decode("utf-8") if node.text else ""


def _walk(node: Node):
    for child in node.children:
        yield child
        yield from _walk(child)


def _complexity(node: Node) -> int:
    count = 1
    for child in _walk(node):
        if child.type in COMPLEXITY_NODE_TYPES:
            if child.type == "binary_expression":
                op = child.child_by_field_name("operator")
                if op and _text(op) in ("&&", "||", "??"):
                    count += 1
            else:
                count += 1
    return count


def _extract_jsdoc(node: Node) -> str | None:
    """Extract JSDoc comment immediately before a node."""
    # Check the node itself, then its parent (for export_statement wrappers)
    for target in (node, node.parent):
        if target and target.prev_named_sibling and target.prev_named_sibling.type == "comment":
            text = _text(target.prev_named_sibling)
            if text.startswith("/**"):
                # Strip /** ... */
                return text[3:-2].strip().replace("\n * ", "\n").replace("\n *", "\n").strip()
    return None


def _is_exported(node: Node) -> bool:
    """Check if node or its parent is an export statement."""
    if node.parent and node.parent.type in ("export_statement", "export_default_declaration"):
        return True
    # Check if the node itself is wrapped in export_statement
    if node.type == "export_statement":
        return True
    return False


def _extract_ts_params(node: Node) -> list[dict]:
    """Extract parameters from a function's formal_parameters node."""
    params_node = node.child_by_field_name("parameters")
    if params_node is None:
        return []
    params = []
    for child in params_node.children:
        if child.type in ("required_parameter", "optional_parameter"):
            param: dict = {"name": "", "type": None, "default": None}
            pattern = child.child_by_field_name("pattern")
            if pattern:
                param["name"] = _text(pattern)
            else:
                # Try first identifier child
                for sub in child.children:
                    if sub.type == "identifier":
                        param["name"] = _text(sub)
                        break
            type_ann = child.child_by_field_name("type")
            if type_ann:
                param["type"] = _text(type_ann).lstrip(": ").strip()
            value = child.child_by_field_name("value")
            if value:
                param["default"] = _text(value)
            if param["name"] and param["name"] != "this":
                params.append(param)
        elif child.type == "identifier":
            params.append({"name": _text(child), "type": None, "default": None})
        elif child.type == "rest_pattern":
            name = ""
            for sub in child.children:
                if sub.type == "identifier":
                    name = _text(sub)
                    break
            if name:
                params.append({"name": "..." + name, "type": None, "default": None})
    return params


def _extract_return_type(node: Node) -> str | None:
    ret = node.child_by_field_name("return_type")
    if ret:
        return _text(ret).lstrip(": ").strip()
    return None


def _parse_function(node: Node, exported: bool = False) -> ParsedCodeUnit:
    name_node = node.child_by_field_name("name")
    name = _text(name_node) if name_node else "<anonymous>"
    is_async = any(c.type == "async" for c in node.children)
    full_text = _text(node)
    if not is_async:
        is_async = full_text.lstrip().startswith("async ")

    return ParsedCodeUnit(
        type="function",
        name=name,
        line_start=node.start_point[0] + 1,
        line_end=node.end_point[0] + 1,
        params=_extract_ts_params(node),
        return_type=_extract_return_type(node),
        is_async=is_async,
        is_exported=exported or _is_exported(node),
        docstring=_extract_jsdoc(node),
        body_text=full_text,
        complexity=_complexity(node),
    )


def _parse_arrow_function(node: Node, name: str, exported: bool = False) -> ParsedCodeUnit:
    """Parse an arrow function from a variable declarator."""
    is_async = any(c.type == "async" for c in node.children) or _text(node).lstrip().startswith("async")
    return ParsedCodeUnit(
        type="function",
        name=name,
        line_start=node.start_point[0] + 1,
        line_end=node.end_point[0] + 1,
        params=_extract_ts_params(node),
        return_type=_extract_return_type(node),
        is_async=is_async,
        is_exported=exported,
        docstring=None,
        body_text=_text(node),
        complexity=_complexity(node),
    )


def _parse_class(node: Node, exported: bool = False) -> ParsedCodeUnit:
    name_node = node.child_by_field_name("name")
    name = _text(name_node) if name_node else "<anonymous>"

    # Heritage (extends / implements)
    bases = []
    implements = []
    for child in node.children:
        if child.type == "class_heritage":
            for sub in child.children:
                if sub.type == "extends_clause":
                    for val in sub.children:
                        if val.type in ("identifier", "member_expression"):
                            bases.append(_text(val))
                elif sub.type == "implements_clause":
                    for val in sub.children:
                        if val.type in ("identifier", "generic_type", "member_expression", "type_identifier"):
                            implements.append(_text(val))

    # Methods as children
    children = []
    body = node.child_by_field_name("body")
    if body:
        for child in body.children:
            if child.type in ("method_definition", "public_field_definition"):
                if child.type == "method_definition":
                    fn = _parse_function(child, exported=False)
                    children.append(fn)

    return ParsedCodeUnit(
        type="class",
        name=name,
        line_start=node.start_point[0] + 1,
        line_end=node.end_point[0] + 1,
        is_exported=exported or _is_exported(node),
        docstring=_extract_jsdoc(node),
        body_text=_text(node),
        children=children,
        base_classes=bases,
        implements=implements,
        complexity=_complexity(node),
    )


def _parse_interface(node: Node, exported: bool = False) -> ParsedCodeUnit:
    name_node = node.child_by_field_name("name")
    name = _text(name_node) if name_node else "<anonymous>"
    return ParsedCodeUnit(
        type="interface",
        name=name,
        line_start=node.start_point[0] + 1,
        line_end=node.end_point[0] + 1,
        is_exported=exported or _is_exported(node),
        docstring=_extract_jsdoc(node),
        body_text=_text(node),
    )


def _parse_import(node: Node) -> list[ParsedImport]:
    """Parse import/require statements."""
    results: list[ParsedImport] = []

    if node.type == "import_statement":
        source = ""
        names: list[str] = []

        for child in node.children:
            if child.type == "string":
                source = _text(child).strip("\"'")
            elif child.type == "import_clause":
                for sub in child.children:
                    if sub.type == "identifier":
                        names.append(_text(sub))  # default import
                    elif sub.type == "named_imports":
                        for spec in sub.children:
                            if spec.type == "import_specifier":
                                name_node = spec.child_by_field_name("name")
                                if name_node:
                                    names.append(_text(name_node))
                    elif sub.type == "namespace_import":
                        for s in sub.children:
                            if s.type == "identifier":
                                names.append("* as " + _text(s))

        if source:
            is_relative = source.startswith(".")
            results.append(ParsedImport(source=source, imported_names=names or ["*"], is_relative=is_relative))

    return results


def _parse_top_level_variable(node: Node, exported: bool = False) -> tuple[list[dict], list[ParsedCodeUnit]]:
    """Parse variable declarations; return (variables, arrow_function_units)."""
    variables: list[dict] = []
    functions: list[ParsedCodeUnit] = []

    if node.type not in ("lexical_declaration", "variable_declaration"):
        return variables, functions

    is_const = any(_text(c) == "const" for c in node.children)

    for child in node.children:
        if child.type == "variable_declarator":
            name_node = child.child_by_field_name("name")
            value_node = child.child_by_field_name("value")
            name = _text(name_node) if name_node else ""
            if not name:
                continue

            # Check if the value is an arrow function
            if value_node and value_node.type == "arrow_function":
                fn = _parse_arrow_function(value_node, name, exported=exported)
                fn.docstring = _extract_jsdoc(node)
                functions.append(fn)
            else:
                type_ann = child.child_by_field_name("type")
                value_text = _text(value_node) if value_node else None
                variables.append({
                    "name": name,
                    "type_annotation": _text(type_ann).lstrip(": ").strip() if type_ann else None,
                    "is_constant": is_const,
                    "value_preview": (value_text[:80] + "...") if value_text and len(value_text) > 80 else value_text,
                })

    return variables, functions


class TypeScriptParser(CodeParser):
    """TypeScript/JavaScript parser using tree-sitter."""

    def __init__(self) -> None:
        self._ts_parser = Parser(TS_LANGUAGE)
        self._tsx_parser = Parser(TSX_LANGUAGE)
        self._js_parser = Parser(JS_LANGUAGE)

    def supported_extensions(self) -> list[str]:
        return [".ts", ".tsx", ".js", ".jsx"]

    def _get_parser(self, file_path: str) -> Parser:
        if file_path.endswith(".tsx") or file_path.endswith(".jsx"):
            return self._tsx_parser
        if file_path.endswith(".js"):
            return self._js_parser
        return self._ts_parser

    def parse(self, file_path: str, content: str) -> ParsedFile:
        parser = self._get_parser(file_path)
        tree = parser.parse(content.encode("utf-8"))
        root = tree.root_node

        imports: list[ParsedImport] = []
        code_units: list[ParsedCodeUnit] = []
        variables: list[dict] = []

        for child in root.children:
            exported = child.type == "export_statement"
            # For export statements, drill into the declaration
            targets = [child]
            if exported:
                targets = [c for c in child.children if c.type not in ("export", "default", ";")]
                if not targets:
                    targets = [child]

            for target in targets:
                if target.type in ("function_declaration", "generator_function_declaration"):
                    code_units.append(_parse_function(target, exported=exported))

                elif target.type == "class_declaration":
                    code_units.append(_parse_class(target, exported=exported))

                elif target.type in ("interface_declaration", "type_alias_declaration"):
                    code_units.append(_parse_interface(target, exported=exported))

                elif target.type in ("lexical_declaration", "variable_declaration"):
                    vars_, fns = _parse_top_level_variable(target, exported=exported)
                    variables.extend(vars_)
                    code_units.extend(fns)

                elif target.type == "import_statement":
                    imports.extend(_parse_import(target))

                elif target.type == "export_statement" and target == child:
                    # Already handled above via targets
                    pass

        return ParsedFile(
            path=file_path,
            language="typescript" if file_path.endswith((".ts", ".tsx")) else "javascript",
            imports=imports,
            code_units=code_units,
            top_level_variables=variables,
            lines_of_code=content.count("\n") + (1 if content and not content.endswith("\n") else 0),
        )
