import subprocess
import sys
import tempfile
import os
from typing import Any, Optional


class McpToolsMbpp:
    """MCP tools for the MBPP benchmark.

    MBPP tasks run locally (no Docker). The primary tool is run_tests,
    which executes candidate code together with the assert test cases
    in an isolated subprocess and reports the result.
    """

    def __init__(self, containerizer: Optional[Any] = None) -> None:
        self.containerizer = containerizer

    def run_tests(
        self,
        code: str,
        test_list: list[str],
        test_imports: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Execute a candidate function against a list of assert tests.

        The function code, optional imports, and assert statements are
        combined and run in a fresh subprocess so the sandbox process
        is not affected by failures.

        Args:
            code: The Python function definition to test. May include
                import statements at the top. Assert lines are stripped
                automatically so duplicates in test_list do not matter.
            test_list: List of assert statements (e.g.
                ["assert f(1) == 2", "assert f(0) == 0"]).
            test_imports: Optional list of import statements needed by
                the tests (e.g. ["from collections import Counter"]).

        Returns:
            A dict with keys:
                - stdout (str): captured standard output
                - stderr (str): captured standard error / traceback
                - exit_code (int): 0 means all tests passed
                - success (bool): True when exit_code is 0
                - summary (str): human-readable PASSED / FAILED message
        """
        imports = test_imports or []
        parts: list[str] = []

        clean_code_lines = [
            ln for ln in code.splitlines()
            if not ln.strip().startswith("assert ")
        ]
        parts.append("\n".join(clean_code_lines))
        parts.append("")

        if imports:
            parts.extend(imports)
            parts.append("")

        parts.extend(test_list)
        full_code = "\n".join(parts)

        try:
            proc = subprocess.run(
                [sys.executable, "-c", full_code],
                capture_output=True,
                text=True,
                timeout=30,
            )
            passed = proc.returncode == 0
            if passed:
                summary = f"PASSED ({len(test_list)} tests)"
            else:
                # Extract the failing assertion from stderr if possible
                first_error = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "unknown error"
                summary = f"FAILED: {first_error}"
            return {
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "exit_code": proc.returncode,
                "success": passed,
                "summary": summary,
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": "Execution timed out after 30 seconds.",
                "exit_code": -1,
                "success": False,
                "summary": "FAILED: execution timed out after 30 seconds",
            }
        except Exception as exc:
            return {
                "stdout": "",
                "stderr": str(exc),
                "exit_code": -1,
                "success": False,
                "summary": f"FAILED: {exc}",
            }

    def run_code(self, code: str) -> dict[str, Any]:
        """Execute arbitrary Python code in an isolated subprocess.

        Useful for quick experiments or intermediate computations
        during task solving.

        Args:
            code: Python source code to execute.

        Returns:
            A dict with stdout, stderr, exit_code, and success.
        """
        tmp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".py",
                mode="w",
                encoding="utf-8",
                delete=False,
            ) as tmp:
                tmp.write(code)
                tmp_path = tmp.name

            proc = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return {
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "exit_code": proc.returncode,
                "success": proc.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": "Execution timed out after 30 seconds.",
                "exit_code": -1,
                "success": False,
            }
        except Exception as exc:
            return {
                "stdout": "",
                "stderr": str(exc),
                "exit_code": -1,
                "success": False,
            }
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
