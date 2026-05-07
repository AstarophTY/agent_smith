from dataclasses import dataclass
from typing import Optional


@dataclass
class SandboxResult:
    """Result of a sandbox execution.

    Attributes:
        stdout (str): Captured standard output.
        stderr (str): Captured standard error.
        error (Optional[str]): Error message when execution fails.
        final_answer (Optional[str]): Value passed to final_answer, if any.
        timed_out (bool): Whether execution timed out.
        exit_code (Optional[int]): Worker process exit code.
    """
    stdout: str
    stderr: str
    error: Optional[str]
    final_answer: Optional[str]
    timed_out: bool
    exit_code: Optional[int]
