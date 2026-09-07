from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import PurePosixPath
from typing import Any

from adaptive_platform.extraction.models import (
    ExtractedRelationship,
    ExtractedSymbol,
    RelationshipType,
    ResolutionStatus,
    SymbolType,
)
from adaptive_platform.extraction.protocol import (
    ExtractionDocument,
    ExtractionRequest,
    ExtractionResult,
    ExtractorDescriptor,
    ExtractorStatus,
)

EXTRACTOR_NAME = "python-ast"
EXTRACTOR_VERSION = "1.0.0"
HTTP_METHODS = frozenset({"delete", "get", "head", "options", "patch", "post", "put"})


def module_name_for_path(path: PurePosixPath) -> str:
    without_suffix = path.with_suffix("")
    parts = list(without_suffix.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _node_end(node: ast.AST) -> tuple[int, int]:
    return (
        int(getattr(node, "end_lineno", getattr(node, "lineno", 1))),
        int(getattr(node, "end_col_offset", getattr(node, "col_offset", 0))),
    )


def _expression(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except (AttributeError, ValueError):
        return None


def _function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    arguments = ast.unparse(node.args)
    returns = _expression(node.returns)
    prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
    suffix = f" -> {returns}" if returns else ""
    return f"{prefix}({arguments}){suffix}"


def _is_type_checking_test(node: ast.AST) -> bool:
    return (isinstance(node, ast.Name) and node.id == "TYPE_CHECKING") or (
        isinstance(node, ast.Attribute)
        and node.attr == "TYPE_CHECKING"
        and isinstance(node.value, ast.Name)
        and node.value.id == "typing"
    )


def _join_route(prefix: str, path: str) -> str:
    if not prefix:
        return path if path.startswith("/") else f"/{path}"
    if path == "/":
        return f"{prefix.rstrip('/')}/"
    return f"{prefix.rstrip('/')}/{path.lstrip('/')}"


class _ModuleVisitor(ast.NodeVisitor):
    def __init__(self, document: ExtractionDocument, tree: ast.Module) -> None:
        self.document = document
        self.tree = tree
        self.module_name = module_name_for_path(document.path)
        self.symbols: list[ExtractedSymbol] = []
        self.relationships: list[ExtractedRelationship] = []
        self.scope: list[tuple[str, SymbolType]] = []
        self.import_bindings: dict[str, str] = {}
        self.type_checking = False
        self.router_prefixes = self._router_prefixes()

    def run(self) -> tuple[list[ExtractedSymbol], list[ExtractedRelationship]]:
        module_end_line, module_end_column = (
            _node_end(self.tree.body[-1]) if self.tree.body else (1, 0)
        )
        self.symbols.append(
            ExtractedSymbol(
                file_id=self.document.file_id,
                name=self.module_name.rsplit(".", 1)[-1],
                qualified_name=self.module_name,
                symbol_type=SymbolType.MODULE,
                signature=None,
                docstring=ast.get_docstring(self.tree, clean=False),
                start_line=1,
                start_column=0,
                end_line=module_end_line,
                end_column=module_end_column,
                extractor_name=EXTRACTOR_NAME,
                extractor_version=EXTRACTOR_VERSION,
                extension_metadata={"language": "Python"},
            )
        )
        self.visit(self.tree)
        self._extract_exports()
        return self.symbols, self.relationships

    @property
    def current_qualified_name(self) -> str:
        return self.scope[-1][0] if self.scope else self.module_name

    def _router_prefixes(self) -> dict[str, str]:
        prefixes: dict[str, str] = {}
        for statement in self.tree.body:
            if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
                continue
            value = statement.value
            if not isinstance(value, ast.Call):
                continue
            callable_name = _expression(value.func)
            if not callable_name or callable_name.rsplit(".", 1)[-1] not in {
                "APIRouter",
                "FastAPI",
            }:
                continue
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            prefix = ""
            for keyword in value.keywords:
                if (
                    keyword.arg == "prefix"
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, str)
                ):
                    prefix = keyword.value.value
            for target in targets:
                if isinstance(target, ast.Name):
                    prefixes[target.id] = prefix
        return prefixes

    def _add_symbol(
        self,
        node: ast.AST,
        *,
        name: str,
        qualified_name: str,
        symbol_type: SymbolType,
        signature: str | None = None,
        docstring: str | None = None,
        parent: str | None = None,
        metadata: dict[str, Any] | None = None,
        start_line: int | None = None,
        start_column: int | None = None,
    ) -> None:
        end_line, end_column = _node_end(node)
        self.symbols.append(
            ExtractedSymbol(
                file_id=self.document.file_id,
                name=name,
                qualified_name=qualified_name,
                symbol_type=symbol_type,
                signature=signature,
                docstring=docstring,
                start_line=start_line or int(getattr(node, "lineno", 1)),
                start_column=(
                    start_column
                    if start_column is not None
                    else int(getattr(node, "col_offset", 0))
                ),
                end_line=end_line,
                end_column=end_column,
                extractor_name=EXTRACTOR_NAME,
                extractor_version=EXTRACTOR_VERSION,
                parent_qualified_name=parent,
                extension_metadata=metadata or {},
            )
        )

    def _add_relationship(
        self,
        node: ast.AST,
        *,
        relationship_type: RelationshipType,
        source: str,
        target: str | None,
        unresolved_target: str | None = None,
        resolution_reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        end_line, end_column = _node_end(node)
        self.relationships.append(
            ExtractedRelationship(
                source_qualified_name=source,
                relationship_type=relationship_type,
                evidence_file_id=self.document.file_id,
                evidence_start_line=int(getattr(node, "lineno", 1)),
                evidence_start_column=int(getattr(node, "col_offset", 0)),
                evidence_end_line=end_line,
                evidence_end_column=end_column,
                resolution_status=(
                    ResolutionStatus.UNRESOLVED
                    if unresolved_target is not None
                    else ResolutionStatus.PARTIALLY_RESOLVED
                ),
                extractor_name=EXTRACTOR_NAME,
                extractor_version=EXTRACTOR_VERSION,
                target_qualified_name=target,
                unresolved_target=unresolved_target,
                resolution_reason=resolution_reason,
                extension_metadata=metadata or {},
            )
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qualified_name = f"{self.current_qualified_name}.{node.name}"
        parent = self.current_qualified_name
        bases = [value for base in node.bases if (value := _expression(base))]
        self._add_symbol(
            node,
            name=node.name,
            qualified_name=qualified_name,
            symbol_type=SymbolType.CLASS,
            docstring=ast.get_docstring(node, clean=False),
            parent=parent,
            metadata={
                "decorators": [
                    value for item in node.decorator_list if (value := _expression(item))
                ],
                "bases": bases,
            },
        )
        for base in node.bases:
            expression = _expression(base)
            if not expression:
                continue
            target = self.import_bindings.get(expression, expression)
            self._add_relationship(
                base,
                relationship_type=RelationshipType.INHERITS,
                source=qualified_name,
                target=target,
                metadata={"expression": expression},
            )
        self.scope.append((qualified_name, SymbolType.CLASS))
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        parent = self.current_qualified_name
        qualified_name = f"{parent}.{node.name}"
        symbol_type = (
            SymbolType.METHOD
            if self.scope and self.scope[-1][1] is SymbolType.CLASS
            else SymbolType.FUNCTION
        )
        decorators = [value for item in node.decorator_list if (value := _expression(item))]
        self._add_symbol(
            node,
            name=node.name,
            qualified_name=qualified_name,
            symbol_type=symbol_type,
            signature=_function_signature(node),
            docstring=ast.get_docstring(node, clean=False),
            parent=parent,
            metadata={"decorators": decorators, "is_async": isinstance(node, ast.AsyncFunctionDef)},
        )
        self._extract_routes(node, qualified_name)
        self.scope.append((qualified_name, symbol_type))
        self.generic_visit(node)
        self.scope.pop()

    def _extract_routes(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        handler: str,
    ) -> None:
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            method = decorator.func.attr.lower()
            if method not in HTTP_METHODS or not isinstance(decorator.func.value, ast.Name):
                continue
            router_name = decorator.func.value.id
            if router_name not in self.router_prefixes or not decorator.args:
                continue
            raw_path = decorator.args[0]
            if not isinstance(raw_path, ast.Constant) or not isinstance(raw_path.value, str):
                continue
            route_path = _join_route(self.router_prefixes[router_name], raw_path.value)
            route_name = f"{method.upper()} {route_path}"
            route_qualified_name = f"{self.module_name}.{route_name}"
            self._add_symbol(
                node,
                name=route_name,
                qualified_name=route_qualified_name,
                symbol_type=SymbolType.ROUTE,
                parent=self.module_name,
                metadata={
                    "method": method.upper(),
                    "path": route_path,
                    "handler": handler,
                    "decorator_line": decorator.lineno,
                    "handler_line": node.lineno,
                },
                start_line=decorator.lineno,
                start_column=decorator.col_offset,
            )

    def visit_Assign(self, node: ast.Assign) -> None:
        if not self.scope:
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    qualified_name = f"{self.module_name}.{target.id}"
                    self._add_symbol(
                        node,
                        name=target.id,
                        qualified_name=qualified_name,
                        symbol_type=SymbolType.CONSTANT,
                        signature=_expression(node.value),
                        parent=self.module_name,
                    )
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if not self.scope and isinstance(node.target, ast.Name) and node.target.id.isupper():
            qualified_name = f"{self.module_name}.{node.target.id}"
            self._add_symbol(
                node,
                name=node.target.id,
                qualified_name=qualified_name,
                symbol_type=SymbolType.CONSTANT,
                signature=_expression(node.annotation),
                parent=self.module_name,
            )
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            binding = alias.asname or alias.name.split(".", 1)[0]
            self.import_bindings[binding] = alias.name
            self._add_relationship(
                node,
                relationship_type=RelationshipType.IMPORTS,
                source=self.module_name,
                target=alias.name,
                metadata={"alias": alias.asname, "type_checking": self.type_checking},
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = self._absolute_import_module(node)
        for alias in node.names:
            target = f"{module}.{alias.name}" if module else alias.name
            binding = alias.asname or alias.name
            self.import_bindings[binding] = target
            self._add_relationship(
                node,
                relationship_type=RelationshipType.IMPORTS,
                source=self.module_name,
                target=target,
                metadata={"alias": alias.asname, "type_checking": self.type_checking},
            )

    def _absolute_import_module(self, node: ast.ImportFrom) -> str:
        if node.level == 0:
            return node.module or ""
        package = (
            self.module_name
            if self.document.path.name == "__init__.py"
            else self.module_name.rsplit(".", 1)[0]
        )
        parts = package.split(".") if package else []
        keep = max(0, len(parts) - (node.level - 1))
        base = parts[:keep]
        if node.module:
            base.extend(node.module.split("."))
        return ".".join(base)

    def visit_If(self, node: ast.If) -> None:
        if not _is_type_checking_test(node.test):
            self.generic_visit(node)
            return
        previous = self.type_checking
        self.type_checking = True
        for statement in node.body:
            self.visit(statement)
        self.type_checking = previous
        for statement in node.orelse:
            self.visit(statement)

    def visit_Call(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
            and _expression(node.func.value) in {"importlib", "importlib.util"}
            and node.args
            and not (isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str))
        ):
            expression = _expression(node) or "dynamic import"
            self._add_relationship(
                node,
                relationship_type=RelationshipType.REFERENCES,
                source=self.module_name,
                target=None,
                unresolved_target=expression,
                resolution_reason="dynamic_import_target",
                metadata={"expression": expression},
            )
        self.generic_visit(node)

    def _extract_exports(self) -> None:
        for statement in self.tree.body:
            if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
                continue
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            if not any(
                isinstance(target, ast.Name) and target.id == "__all__" for target in targets
            ):
                continue
            value = statement.value
            if not isinstance(value, (ast.List, ast.Tuple, ast.Set)):
                continue
            for element in value.elts:
                if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
                    continue
                target = self.import_bindings.get(
                    element.value, f"{self.module_name}.{element.value}"
                )
                self._add_relationship(
                    element,
                    relationship_type=RelationshipType.EXPOSES,
                    source=self.module_name,
                    target=target,
                    metadata={"exported_name": element.value},
                )


class PythonAstExtractor:
    descriptor = ExtractorDescriptor(
        name=EXTRACTOR_NAME,
        version=EXTRACTOR_VERSION,
        languages=("Python",),
        status=ExtractorStatus.SUPPORTED,
    )

    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        symbols: list[ExtractedSymbol] = []
        relationships: list[ExtractedRelationship] = []
        diagnostics: list[str] = []
        for document in sorted(request.documents, key=lambda item: item.path.as_posix()):
            try:
                tree = ast.parse(document.content, filename=document.path.as_posix())
            except (SyntaxError, ValueError) as exc:
                line = getattr(exc, "lineno", None)
                diagnostics.append(f"{document.path.as_posix()}:{line or 1}:syntax_error")
                continue
            module_symbols, module_relationships = _ModuleVisitor(document, tree).run()
            symbols.extend(module_symbols)
            relationships.extend(module_relationships)

        symbol_names = {item.qualified_name for item in symbols}
        repository_roots = {
            module_name_for_path(document.path).split(".", 1)[0]
            for document in request.documents
            if module_name_for_path(document.path)
        }
        resolved_relationships = tuple(
            self._resolve_relationship(item, symbol_names, repository_roots)
            for item in relationships
        )
        return ExtractionResult(
            status=ExtractorStatus.PARTIAL if diagnostics else ExtractorStatus.SUPPORTED,
            symbols=tuple(symbols),
            relationships=resolved_relationships,
            diagnostics=tuple(diagnostics),
        )

    @staticmethod
    def _resolve_relationship(
        relationship: ExtractedRelationship,
        symbol_names: set[str],
        repository_roots: set[str],
    ) -> ExtractedRelationship:
        target = relationship.target_qualified_name
        if relationship.unresolved_target is not None:
            return relationship
        if target in symbol_names:
            return replace(
                relationship,
                resolution_status=ResolutionStatus.RESOLVED,
                resolution_reason=None,
            )
        root = target.split(".", 1)[0] if target else ""
        reason = "local_target_not_extracted" if root in repository_roots else "external_dependency"
        return replace(
            relationship,
            target_qualified_name=None,
            unresolved_target=target,
            resolution_status=ResolutionStatus.UNRESOLVED,
            resolution_reason=reason,
        )
