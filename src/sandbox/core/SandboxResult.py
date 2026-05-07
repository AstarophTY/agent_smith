from dataclasses import dataclass
from typing import Optional


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    error: Optional[str]
    final_answer: Optional[str]
    timed_out: bool
    exit_code: Optional[int]
