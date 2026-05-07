import ast
from fnmatch import fnmatch
from typing import Any, Iterable, Set

from .SecurityException import SecurityException


class ImportAllowlistValidator(ast.NodeVisitor):
    """AST validator that enforces allowlists for imports and calls.

    Args:
        authorized_imports (Iterable[str]): Allowed import patterns.
        allowed_calls (Iterable[str]): Allowed callable names.
        allowed_attribute_bases (Iterable[str]): Allowed base names for
            attribute calls.
    """

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
        """Validate code by walking the AST.

        Args:
            code (str): Python source code to validate.

        Raises:
            SecurityException: If an import or call is not allowed.
        """
        tree = ast.parse(code, mode="exec")
        self.visit(tree)

    def visit_Import(self, node: ast.Import) -> Any:
        """Validate import statements.

        Args:
            node (ast.Import): Import node.

        Raises:
            SecurityException: If an import is not allowed.
        """
        for alias in node.names:
            if not self.is_allowed_import(self.authorized_imports, alias.name):
                raise SecurityException(f"Import not allowed: {alias.name}")
            base_name = (alias.asname or alias.name).split(".")[0]
            self.allowed_attribute_bases.add(base_name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        """Validate from-import statements.

        Args:
            node (ast.ImportFrom): ImportFrom node.

        Raises:
            SecurityException: If a module or symbol is not allowed.
        """
        if node.module is None or node.level and node.level > 0:
            raise SecurityException("Relative imports are not allowed")
        module_name = node.module
        for alias in node.names:
            full_name = f"{module_name}.{alias.name}"
            if not (
                self.is_allowed_import(self.authorized_imports, module_name)
                or self.is_allowed_import(self.authorized_imports, full_name)
            ):
                raise SecurityException(f"Import not allowed: {full_name}")
            name = alias.asname or alias.name
            self.allowed_calls.add(name)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        """Validate call expressions.

        Args:
            node (ast.Call): Call node.

        Raises:
            SecurityException: If a call is not allowed.
        """
        func = node.func
        if isinstance(func, ast.Name):
            if func.id not in self.allowed_calls:
                raise SecurityException(f"Call not allowed: {func.id}")
        elif isinstance(func, ast.Attribute) \
                and isinstance(func.value, ast.Name):
            if func.value.id not in self.allowed_attribute_bases:
                raise SecurityException(
                    f"Call not allowed: {func.value.id}.{func.attr}"
                )
        else:
            raise SecurityException("Call not allowed")
        self.generic_visit(node)

    @staticmethod
    def is_allowed_import(
        authorized_imports: Iterable[str],
        module_name: str
    ) -> bool:
        """Check whether a module name matches an allowed import pattern.

        Args:
            authorized_imports (Iterable[str]): Allowed import patterns.
            module_name (str): Module name to check.

        Returns:
            bool: True if the module name is allowed.
        """
        return any(
            fnmatch(module_name, pattern) for pattern in authorized_imports
        )
