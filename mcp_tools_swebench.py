import ast
from fnmatch import fnmatch
import os
import re
import shlex
from pathlib import Path
from typing import Any, Optional


Symbol = dict[str, Any]


class McpToolsSweBench:
    def __init__(self, containerizer: Optional[Any] = None) -> None:
        self.containerizer = containerizer

    def run_command(
        self,
        command: str,
        workdir: str,
    ) -> dict[str, str]:
        """Execute a shell command in the specified working directory.

        Args:
            command: The command string to execute.
            workdir: The working directory where the command will be run.

        Returns:
            A dictionary containing 'stdout' and 'stderr'.
        """
        if not self.containerizer:
            raise RuntimeError("Containerizer is not initialized. Operations on the host machine are disabled.")

        full_command = f"cd {shlex.quote(workdir)} && {command}"
        return self.containerizer.cmd(full_command)

    def read_file(self, filepath: str, start_line: int, end_line: int) -> str:
        """Read specific lines from a file with line numbers.

        Args:
            filepath: Path to the file to read.
            start_line: Starting line number (1-indexed).
            end_line: Ending line number (1-indexed, inclusive).

        Returns:
            A string containing the requested lines with line numbers prefixed.
        """
        if not self.containerizer:
            raise RuntimeError("Containerizer is not initialized. Operations on the host machine are disabled.")

        # Use sed to read specific lines in the container
        cmd = f"sed -n '{start_line},{end_line}p' {shlex.quote(filepath)}"
        result = self.containerizer.cmd(cmd)
        lines = result["stdout"].splitlines(keepends=True)

        return "".join(
            f"{line_number + start_line}: {line_content}"
            for line_number, line_content in enumerate(lines)
        )

    def edit_file(self, filepath: str, old_str: str, new_str: str) -> None:
        """Replace text content in a file.

        Args:
            filepath: Path to the file to edit.
            old_str: The text to search for and replace.
            new_str: The replacement text.
        """
        if not self.containerizer:
            raise RuntimeError("Containerizer is not initialized. Operations on the host machine are disabled.")

        # For simplicity, we can read the file, modify it locally, and write it back
        # or use sed if possible. But reading/writing might be safer for complex strings.
        read_cmd = f"cat {shlex.quote(filepath)}"
        content = self.containerizer.cmd(read_cmd)["stdout"]
        new_content = content.replace(old_str, new_str)
        
        # Write back using a temporary file and base64 to avoid shell escape issues
        import base64
        b64_content = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")
        write_cmd = f"echo {b64_content} | base64 -d > {shlex.quote(filepath)}"
        self.containerizer.cmd(write_cmd)

    def list_files(self, directory: str, pattern: str) -> list[str]:
        """List files matching a pattern in a directory recursively.

        Args:
            directory: The root directory to search.
            pattern: A fnmatch pattern to filter files.
                Empty string matches all files.

        Returns:
            A list of file paths matching the pattern.
        """
        if not self.containerizer:
            raise RuntimeError("Containerizer is not initialized. Operations on the host machine are disabled.")

        # Use find in the container
        if pattern:
            cmd = f"find {shlex.quote(directory)} -name {shlex.quote(pattern)}"
        else:
            cmd = f"find {shlex.quote(directory)} -type f"
        
        result = self.containerizer.cmd(cmd)
        return result["stdout"].splitlines()

    def search_code(self, pattern: str, file_pattern: str) -> str:
        """Search for a regex pattern in files matching a file pattern.

        Args:
            pattern: A regex pattern to search for.
            file_pattern: A fnmatch pattern to filter files to search.

        Returns:
            A string with matching results in format:
                filepath:line_number content.
        """
        if not self.containerizer:
            raise RuntimeError("Containerizer is not initialized. Operations on the host machine are disabled.")

        # Use grep in the container
        # -r: recursive, -n: line number, -E: extended regex
        # --include: filter files
        grep_cmd = f"grep -rnE {shlex.quote(pattern)} ."
        if file_pattern:
            grep_cmd += f" --include={shlex.quote(file_pattern)}"
        
        result = self.containerizer.cmd(grep_cmd)
        return result["stdout"]

    def run_tests(self) -> dict[str, str]:
        """Run the test suite using the agent-smith-test.sh script."""
        return self.run_command("sh agent-smith-test.sh", ".")

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

    def _parse_python_symbols(
        self,
        directory: str,
        include_references: bool = True,
    ) -> dict[str, Any]:
        """Parse Python symbols (definitions/references) in a directory.

        Returns a dict with keys: `definitions`, `references`, `errors`.
        """
        definitions_map: dict[str, list[Symbol]] = {}
        references_map: dict[str, list[Symbol]] = {}
        errors: list[str] = []

        files = self.list_files(directory, "*.py")

        for file_path in files:
            try:
                if not self.containerizer:
                    raise RuntimeError("Containerizer is not initialized.")
                code = self.containerizer.cmd(f"cat {shlex.quote(file_path)}")["stdout"]
                tree = ast.parse(code, filename=str(file_path))
            except (OSError, SyntaxError, UnicodeDecodeError) as error:
                errors.append(f"Error parsing {file_path}: {error}")
                continue

            file_key = str(Path(file_path))
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

    def search_function_or_class_definition_in_code(
        self,
        name: str,
        directory: str = ".",
    ) -> str:
        """Find the definition of a function or a class.

        The output format matches `search_code` lines:
        filepath:line_number content
        """
        data = self._parse_python_symbols(
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
                    if not self.containerizer:
                        raise RuntimeError("Containerizer is not initialized.")
                    code = self.containerizer.cmd(f"cat {shlex.quote(file_path)}")["stdout"]
                    line = code.splitlines()[line_no - 1]
                except Exception:
                    line = ""
                matches.append(
                    f"{file_path}:{line_no} {line.rstrip()}"
                )

        return "\n".join(matches)

    def find_references(
        self,
        name: str,
        directory: str = ".",
    ) -> str:
        """Find all usages of a symbol (function or class).

        Returns lines in the same format as `search_code`.
        """
        data = self._parse_python_symbols(
            directory,
            include_references=True,
        )
        refs = data.get("references", {})
        matches: list[str] = []

        for file_path, items in refs.items():
            for item in items:
                if item.get("name") != name:
                    continue
                line_no = item.get("line", 0)
                try:
                    if not self.containerizer:
                        raise RuntimeError("Containerizer is not initialized.")
                    code = self.containerizer.cmd(f"cat {shlex.quote(file_path)}")["stdout"]
                    line = code.splitlines()[line_no - 1]
                except Exception:
                    line = ""
                matches.append(
                    f"{file_path}:{line_no} {line.rstrip()}"
                )

        return "\n".join(matches)
