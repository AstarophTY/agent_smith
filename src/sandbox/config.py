import json
from typing import List

from pydantic import BaseModel, Field


class SandboxConfig(BaseModel):
    """Configuration for the secure code execution sandbox."""

    authorized_imports: List[str] = Field(default_factory=lambda: [
        "math", "math.*",
        "collections", "collections.*",
        "itertools", "re", "json",
        "typing", "typing.*",
        "functools", "operator",
        "heapq", "bisect", "copy",
        "string", "random",
        "datetime", "datetime.*",
        "array", "cmath",
    ])
    allowed_directories: List[str] = Field(default_factory=lambda: [
        "/testbed", "/tmp/agent",
    ])
    max_execution_time_seconds: int = Field(default=30)
    max_memory_mb: int = Field(default=512)


def load_config(path: str) -> SandboxConfig:
    """Load sandbox configuration from a JSON file."""
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if hasattr(SandboxConfig, "model_validate"):
        return SandboxConfig.model_validate(data)
    return SandboxConfig.parse_obj(data)
