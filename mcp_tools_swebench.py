import ast
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
    ) -> dict[str, Any]:
        """Execute a shell command in the specified working directory.

        Args:
            command: The command string to execute.
            workdir: The working directory where the command will run.

        Returns:
            A dictionary containing 'stdout', 'stderr', and 'exit_code'.
        """
        if not self.containerizer:
            raise RuntimeError("Containerizer is not initialized.")
        full_command = f"cd {shlex.quote(workdir)} && {command}"
        return self.containerizer.cmd(full_command)

    def read_file(
        self, filepath: str, start_line: int, end_line: int
    ) -> str:
        """Read specific lines from a file with line numbers.

        Args:
            filepath: Path to the file to read.
            start_line: Starting line number (1-indexed).
            end_line: Ending line number (1-indexed, inclusive).

        Returns:
            Lines with format '<line_number>: <line_content>'.
            Returns an error message if the file cannot be read.
        """
        if not self.containerizer:
            raise RuntimeError("Containerizer is not initialized.")

        try:
            start_line = int(start_line)
            end_line = int(end_line)
        except (TypeError, ValueError):
            return (
                f"[ERROR] read_file expects integer line numbers, got "
                f"start_line={start_line!r} end_line={end_line!r}. "
                "Pass integers without quotes."
            )
        if start_line < 1 or end_line < start_line:
            return (
                f"[ERROR] Invalid range start_line={start_line} "
                f"end_line={end_line}. Must satisfy 1 <= start <= end."
            )

        cmd = f"sed -n '{start_line},{end_line}p' {shlex.quote(filepath)}"
        result = self.containerizer.cmd(cmd)
        if result.get("exit_code", 0) != 0 and result.get("stderr"):
            return f"[ERROR] Could not read {filepath}: {result['stderr']}"
        lines = result["stdout"].splitlines(keepends=True)
        if not lines:
            return f"[INFO] File {filepath} is empty or range {start_line}-{end_line} has no content."
        return "".join(
            f"{line_number + start_line}: {line_content}"
            for line_number, line_content in enumerate(lines)
        )

    def edit_file(
        self, filepath: str, old_str: str, new_str: str
    ) -> str:
        """Replace an exact string in a file with a new string.

        Args:
            filepath: Path to the file to edit.
            old_str: The text to search for and replace.
            new_str: The replacement text.

        Returns:
            A confirmation message or an error description.
        """
        if not self.containerizer:
            raise RuntimeError("Containerizer is not initialized.")

        read_cmd = f"cat {shlex.quote(filepath)}"
        result = self.containerizer.cmd(read_cmd)
        if result.get("exit_code", 0) != 0:
            return f"[ERROR] Could not read {filepath}: {result.get('stderr', '')}"

        content = result["stdout"]
        if old_str not in content:
            occurrences = content.count(old_str)
            return (
                f"[ERROR] old_str not found in {filepath}. "
                "Verify the exact string including whitespace and indentation."
            )

        occurrences = content.count(old_str)
        if occurrences > 1:
            return (
                f"[ERROR] old_str appears {occurrences} times in {filepath}. "
                "Provide more context to make it unique."
            )

        new_content = content.replace(old_str, new_str, 1)

        import base64
        b64_content = base64.b64encode(
            new_content.encode("utf-8")
        ).decode("utf-8")
        write_cmd = (
            f"echo {b64_content} | base64 -d > {shlex.quote(filepath)}"
        )
        write_result = self.containerizer.cmd(write_cmd)
        if write_result.get("exit_code", 0) != 0:
            return f"[ERROR] Write failed: {write_result.get('stderr', '')}"
        return f"[OK] Edit applied to {filepath} (1 replacement made)."

    def list_files(self, directory: str, pattern: str) -> list[str]:
        """List files matching a pattern in a directory recursively.

        Args:
            directory: The root directory to search.
            pattern: A glob pattern to filter files (empty = all files).

        Returns:
            A list of file paths matching the pattern.
        """
        if not self.containerizer:
            raise RuntimeError("Containerizer is not initialized.")

        if pattern:
            cmd = (
                f"find {shlex.quote(directory)}"
                f" -name {shlex.quote(pattern)}"
            )
        else:
            cmd = f"find {shlex.quote(directory)} -type f"

        result = self.containerizer.cmd(cmd)
        return result["stdout"].splitlines()

    _SEARCH_EXCLUDE_DIRS = (
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        "build",
        "dist",
        ".eggs",
    )
    _SEARCH_MAX_LINES = 100
    _SEARCH_MAX_PER_FILE = 20

    def search_code(self, pattern: str, file_pattern: str = "*.py") -> str:
        """Search for a regex pattern in files matching file_pattern.

        Searches from /testbed by default. Results are returned in format:
        /absolute/path/to/file.py:<line_number>:<line_content>

        Args:
            pattern: A regex pattern to search for.
            file_pattern: A glob pattern to filter files (default: *.py).

        Returns:
            Matching lines in format '/path/to/file.py:<line>:<content>'.
            Returns a message if no matches are found.
        """
        if not self.containerizer:
            raise RuntimeError("Containerizer is not initialized.")

        parts = [
            "grep",
            "-rnEI",
            "--color=never",
            f"-m {self._SEARCH_MAX_PER_FILE}",
        ]
        parts.extend(f"--exclude-dir={d}" for d in self._SEARCH_EXCLUDE_DIRS)
        if file_pattern:
            parts.append(f"--include={shlex.quote(file_pattern)}")
        parts.append(shlex.quote(pattern))
        parts.append("/testbed")
        # head -N+1 lets us detect truncation without a second pass.
        grep_cmd = (
            " ".join(parts)
            + f" 2>/dev/null | head -{self._SEARCH_MAX_LINES + 1}"
        )

        output = self.containerizer.cmd(grep_cmd)["stdout"]
        if not output.strip():
            return f"[INFO] No matches found for pattern '{pattern}' in /testbed."

        lines = output.splitlines()
        if len(lines) > self._SEARCH_MAX_LINES:
            kept = "\n".join(lines[: self._SEARCH_MAX_LINES])
            return (
                f"{kept}\n[INFO] Output truncated at {self._SEARCH_MAX_LINES} lines. "
                "Refine the pattern or file_pattern for narrower results."
            )
        return "\n".join(lines)

    def run_tests(self) -> dict[str, Any]:
        """Run the evaluation test suite (agent-smith-test.sh).

        Returns a dict with stdout, stderr, exit_code, passed (bool), summary.
        Detects Django unittest, pytest, and generic 'Test passed/failed'
        formats. Never trusts exit_code alone because SWE-bench eval scripts
        often exit 0 even when tests fail, and never trusts a lone 'OK'
        because Django prints 'OK' for every migration step.
        """
        import re

        result = self.run_command("bash agent-smith-test.sh", "/testbed")
        exit_code = result.get("exit_code", -1)
        stdout = result.get("stdout", "") or ""
        stderr = result.get("stderr", "") or ""
        combined = f"{stdout}\n{stderr}"

        django_pass = re.search(r"Ran \d+ tests? in [\d.]+s\s*\nOK\b", combined)
        django_fail = re.search(r"Ran \d+ tests? in [\d.]+s\s*\nFAILED", combined)
        pytest_pass = re.search(r"=+\s*\d+ passed.*in [\d.]+s", combined)
        pytest_fail = re.search(r"\d+ failed", combined)
        has_traceback = "Traceback (most recent call last)" in combined
        placeholder_fail = re.search(r"^Test failed\s*$", combined, re.MULTILINE)
        placeholder_pass = re.search(r"^Test passed\s*$", combined, re.MULTILINE)

        if django_fail or pytest_fail or placeholder_fail or has_traceback:
            passed = False
            reason = "test runner reported failures"
        elif django_pass or pytest_pass or placeholder_pass:
            passed = True
            reason = "test runner reported all passing"
        elif exit_code != 0:
            passed = False
            reason = f"non-zero exit_code={exit_code} and no test summary found"
        else:
            passed = False
            reason = "no Django/pytest summary found — cannot confirm success"

        result["passed"] = passed
        if passed:
            result["summary"] = f"ALL TESTS PASSED ({reason})"
        else:
            result["summary"] = (
                f"TESTS FAILED ({reason}) — read stdout/stderr for details"
            )
        return result

    def get_patch(self) -> str:
        """Retrieve the unified git diff of all changes in the repository.

        Produces a patch that can be passed directly to final_answer().
        Use 'git -c core.fileMode=false diff HEAD' to get file-mode-agnostic diff.

        Returns:
            A string containing the unified diff (empty if no changes).
        """
        if not self.containerizer:
            raise RuntimeError(
                "Containerizer is not initialized. "
                "Cannot retrieve patch from Docker container."
            )
        result = self.containerizer.cmd(
            "git -c core.fileMode=false diff HEAD"
            " --no-color --diff-algorithm=minimal"
        )
        patch = result.get("stdout", "")
        if not patch.strip():
            return "[INFO] No changes detected (empty patch)."
        return patch

    @staticmethod
    def _payload(node: ast.AST, kind: str, name: str) -> Symbol:
        line = getattr(node, "lineno", 1)
        column = getattr(node, "col_offset", 0)
        end_line = getattr(node, "end_lineno", line)
        end_column = getattr(
            node, "end_col_offset", column + len(name)
        )
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
        """Parse Python symbols in a directory.

        Returns a dict with keys: definitions, references, errors.
        """
        definitions_map: dict[str, list[Symbol]] = {}
        references_map: dict[str, list[Symbol]] = {}
        errors: list[str] = []

        files = self.list_files(directory, "*.py")

        for file_path in files:
            try:
                if not self.containerizer:
                    raise RuntimeError("Containerizer is not initialized.")
                code = self.containerizer.cmd(
                    f"cat {shlex.quote(file_path)}"
                )["stdout"]
                tree = ast.parse(code, filename=str(file_path))
            except (OSError, SyntaxError, UnicodeDecodeError) as err:
                errors.append(f"Error parsing {file_path}: {err}")
                continue

            file_key = str(Path(file_path))
            defs: list[Symbol] = []
            refs: list[Symbol] = []
            parents: dict[ast.AST, ast.AST] = {}

            class Collector(ast.NodeVisitor):
                def visit(self, node: ast.AST) -> Any:
                    for child in ast.iter_child_nodes(node):
                        parents[child] = node
                    return super().visit(node)

                def visit_FunctionDef(
                    self, node: ast.FunctionDef
                ) -> None:
                    defs.append(
                        McpToolsSweBench._payload(
                            node, "definition.function", node.name
                        )
                    )
                    self.generic_visit(node)

                def visit_AsyncFunctionDef(
                    self, node: ast.AsyncFunctionDef
                ) -> None:
                    defs.append(
                        McpToolsSweBench._payload(
                            node, "definition.function", node.name
                        )
                    )
                    self.generic_visit(node)

                def visit_ClassDef(
                    self, node: ast.ClassDef
                ) -> None:
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
                    kind = (
                        "reference.call" if is_call
                        else "reference.name"
                    )
                    refs.append(
                        McpToolsSweBench._payload(
                            node, kind, node.id
                        )
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
        directory: str = "/testbed",
    ) -> str:
        """Find the definition of a function or a class.

        Searches from /testbed by default.
        Output format: 'filepath:line_number content'

        Args:
            name: Function or class name to find.
            directory: Root directory to search (default: /testbed).
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
                    code = self.containerizer.cmd(
                        f"cat {shlex.quote(file_path)}"
                    )["stdout"]
                    line = code.splitlines()[line_no - 1]
                except Exception:
                    line = ""
                matches.append(
                    f"{file_path}:{line_no} {line.rstrip()}"
                )

        if not matches:
            return f"[INFO] No definition found for '{name}' in {directory}."
        return "\n".join(matches)

    def find_references(
        self,
        name: str,
        directory: str = "/testbed",
    ) -> str:
        """Find all usages of a symbol (function or class).

        Searches from /testbed by default.
        Output format matches search_code format.

        Args:
            name: Symbol name to find references for.
            directory: Root directory to search (default: /testbed).
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
                    code = self.containerizer.cmd(
                        f"cat {shlex.quote(file_path)}"
                    )["stdout"]
                    line = code.splitlines()[line_no - 1]
                except Exception:
                    line = ""
                matches.append(
                    f"{file_path}:{line_no} {line.rstrip()}"
                )

        if not matches:
            return f"[INFO] No references found for '{name}' in {directory}."
        return "\n".join(matches)
