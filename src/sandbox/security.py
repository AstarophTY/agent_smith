import ast
from fnmatch import fnmatch
from typing import Any, Iterable, Set

from .exceptions import SecurityException


class ImportAllowlistValidator(ast.NodeVisitor):
    """AST validator that enforces allowlists for imports and calls."""

    def __init__(
        self,
        authorized_imports: Iterable[str],
        allowed_calls: Iterable[str],
        allowed_attribute_bases: Iterable[str],
    ) -> None:
        self.authorized_imports = list(authorized_imports)
        self.allowed_calls: Set[str] = set(allowed_calls)
        self.allowed_attribute_bases: Set[str] = set(allowed_attribute_bases)

    def validate(self, code: str) -> None:
        tree = ast.parse(code, mode="exec")
        self.visit(tree)

    def visit_Import(self, node: ast.Import) -> Any:
        for alias in node.names:
            if not self._is_allowed_import(alias.name):
                raise SecurityException(f"Import not allowed: {alias.name}")
            base_name = (alias.asname or alias.name).split(".")[0]
            self.allowed_attribute_bases.add(base_name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        if node.module is None or node.level and node.level > 0:
            raise SecurityException("Relative imports are not allowed")
        module_name = node.module
        for alias in node.names:
            full_name = f"{module_name}.{alias.name}"
            if not (self._is_allowed_import(module_name) or self._is_allowed_import(full_name)):
                raise SecurityException(f"Import not allowed: {full_name}")
            name = alias.asname or alias.name
            self.allowed_calls.add(name)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        func = node.func
        if isinstance(func, ast.Name):
            if func.id not in self.allowed_calls:
                raise SecurityException(f"Call not allowed: {func.id}")
        elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            if func.value.id not in self.allowed_attribute_bases:
                raise SecurityException(f"Call not allowed: {func.value.id}.{func.attr}")
        else:
            raise SecurityException("Call not allowed")
        self.generic_visit(node)

    def _is_allowed_import(self, module_name: str) -> bool:
        return any(fnmatch(module_name, pattern) for pattern in self.authorized_imports)


def build_allowed_attribute_bases(authorized_imports: Iterable[str]) -> Set[str]:
    bases: Set[str] = set()
    for pattern in authorized_imports:
        base = pattern.split(".")[0]
        if base:
            bases.add(base)
    return bases
