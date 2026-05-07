import ast
from fnmatch import fnmatch
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any


Symbol = dict[str, Any]


class McpToolsSweBench:
    @staticmethod
    def run_command(
        command: str,
        workdir: str,
    ) -> subprocess.CompletedProcess[Any]:
        """Execute a shell command in the specified working directory.

        Args:
            command: The command string to execute.
            workdir: The working directory where the command will be run.

        Returns:
            The result of subprocess.run().
        """
        return subprocess.run(shlex.split(command), cwd=workdir)

    @staticmethod
    def read_file(filepath: str, start_line: int, end_line: int) -> str:
        """Read specific lines from a file with line numbers.

        Args:
            filepath: Path to the file to read.
            start_line: Starting line number (1-indexed).
            end_line: Ending line number (1-indexed, inclusive).

        Returns:
            A string containing the requested lines with line numbers prefixed.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            buffer = f.readlines()
        lines = buffer[start_line - 1:end_line]

        return "".join(
            f"{line_number + start_line}: {line_content}"
            for line_number, line_content in enumerate(lines)
        )

    @staticmethod
    def edit_file(filepath: str, old_str: str, new_str: str) -> None:
        """Replace text content in a file.

        Args:
            filepath: Path to the file to edit.
            old_str: The text to search for and replace.
            new_str: The replacement text.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            buffer = f.read()

        new_content = buffer.replace(old_str, new_str)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)

    @staticmethod
    def list_files(directory: str, pattern: str) -> list[str]:
        """List files matching a pattern in a directory recursively.

        Args:
            directory: The root directory to search.
            pattern: A fnmatch pattern to filter files.
                Empty string matches all files.

        Returns:
            A list of file paths matching the pattern.
        """
        results: list[str] = []
        for root, _, files in os.walk(directory):
            for fname in files:
                if fnmatch(fname, pattern) or len(pattern) <= 0:
                    results.append(os.path.join(root, fname))

        return results

    @staticmethod
    def search_code(pattern: str, file_pattern: str) -> str:
        """Search for a regex pattern in files matching a file pattern.

        Args:
            pattern: A regex pattern to search for.
            file_pattern: A fnmatch pattern to filter files to search.

        Returns:
            A string with matching results in format:
                filepath:line_number content.
        """
        checker = re.compile(pattern)
        matches: list[str] = []

        for root, _, files in os.walk("."):
            for filename in files:
                if not fnmatch(filename, file_pattern):
                    continue

                file_path = os.path.join(root, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as handle:
                        for line_number, line_content in enumerate(
                            handle,
                            start=1,
                        ):
                            if checker.search(line_content):
                                line_path = os.path.abspath(file_path)
                                matches.append(
                                    f"{line_path}:{line_number} "
                                    f"{line_content.rstrip()}"
                                )
                except (UnicodeDecodeError, IOError):
                    continue

        return "\n".join(matches)

    def run_tests(self) -> None:
        """Run the test suite using the agent-smith-test.sh script."""
        self.run_command("sh agent-smith-test.sh", ".")

    @staticmethod
    def _payload(node: ast.AST, kind: str, name: str) -> Symbol:
        line = getattr(node, "lineno", 1)
        column = getattr(node, "col_offset", 0)
        end_line = getattr(node, "end_lineno", line)
        end_column = getattr(node, "end_col_offset", column + len(name))
        return {
            "name": name,
            "type": kind,
            "line": line,
            "column": column,
            "end_line": end_line,
            "end_column": end_column,
        }

    @staticmethod
    def parse_python_symbols(
        directory: str,
        include_references: bool = True,
    ) -> dict[str, Any]:
        """Parse Python symbols (definitions/references) in a directory.

        Returns a dict with keys: `definitions`, `references`, `errors`.
        """
        definitions_map: dict[str, list[Symbol]] = {}
        references_map: dict[str, list[Symbol]] = {}
        errors: list[str] = []

        for file_path in Path(directory).rglob("*.py"):
            if not file_path.is_file():
                continue
            try:
                code = file_path.read_text(encoding="utf-8")
                tree = ast.parse(code, filename=str(file_path))
            except (OSError, SyntaxError, UnicodeDecodeError) as error:
                errors.append(f"Error parsing {file_path}: {error}")
                continue

            file_key = str(file_path.resolve())
            defs: list[Symbol] = []
            refs: list[Symbol] = []
            parents: dict[ast.AST, ast.AST] = {}

            class Collector(ast.NodeVisitor):
                def visit(
                    self,
                    node: ast.AST,
                ) -> Any:
                    for child in ast.iter_child_nodes(node):
                        parents[child] = node
                    return super().visit(node)

                def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                    defs.append(
                        McpToolsSweBench._payload(
                            node, "definition.function", node.name
                        )
                    )
                    self.generic_visit(node)

                def visit_AsyncFunctionDef(
                    self,
                    node: ast.AsyncFunctionDef,
                ) -> None:
                    defs.append(
                        McpToolsSweBench._payload(
                            node, "definition.function", node.name
                        )
                    )
                    self.generic_visit(node)

                def visit_ClassDef(self, node: ast.ClassDef) -> None:
                    defs.append(
                        McpToolsSweBench._payload(
                            node, "definition.class", node.name
                        )
                    )
                    self.generic_visit(node)

                def visit_Name(self, node: ast.Name) -> None:
                    if not include_references:
                        return
                    if not isinstance(node.ctx, ast.Load):
                        return

                    parent = parents.get(node)
                    is_call = (
                        isinstance(parent, ast.Call)
                        and parent.func is node
                    )
                    kind = "reference.call" if is_call else "reference.name"
                    refs.append(
                        McpToolsSweBench._payload(node, kind, node.id)
                    )

            Collector().visit(tree)
            definitions_map[file_key] = defs
            references_map[file_key] = refs

        return {
            "definitions": definitions_map,
            "references": references_map,
            "errors": errors,
        }

    @staticmethod
    def search_function_or_class_definition_in_code(
        name: str,
        directory: str = ".",
    ) -> str:
        """Find the definition of a function or a class.

        The output format matches `search_code` lines:
        filepath:line_number content
        """
        data = McpToolsSweBench.parse_python_symbols(
            directory,
            include_references=False,
        )
        defs = data.get("definitions", {})
        matches: list[str] = []

        for file_path, items in defs.items():
            for item in items:
                if item.get("name") != name:
                    continue
                line_no = item.get("line", 0)
                try:
                    text = Path(file_path).read_text(encoding="utf-8")
                    line = text.splitlines()[line_no - 1]
                except Exception:
                    line = ""
                matches.append(
                    f"{file_path}:{line_no} {line.rstrip()}"
                )

        return "\n".join(matches)

    @staticmethod
    def find_references(
        name: str,
        filepath: str | None = None,
        line: int | None = None,
        directory: str = ".",
    ) -> str:
        """Find all usages of a symbol (function or class).

        Returns lines in the same format as `search_code`.
        If `filepath` and `line` are provided, they are used only for
        reference context (not required).
        """
        data = McpToolsSweBench.parse_python_symbols(
            directory,
            include_references=True,
        )
        refs = data.get("references", {})
        matches: list[str] = []

        if filepath is not None:
            try:
                _ = str(Path(filepath).resolve())
            except Exception:
                _ = None

        for file_path, items in refs.items():
            for item in items:
                if item.get("name") != name:
                    continue
                line_no = item.get("line", 0)
                try:
                    text = Path(file_path).read_text(encoding="utf-8")
                    content = text.splitlines()[line_no - 1]
                except Exception:
                    content = ""
                matches.append(
                    f"{file_path}:{line_no} {content.rstrip()}"
                )

        return "\n".join(matches)
