import json
from typing import List

from pydantic import BaseModel, Field


class SandboxConfig(BaseModel):
    """Sandbox configuration for student solutions."""
    authorized_imports: List[str] = Field(default_factory=list)
    authorized_calls: List[str] = Field(default_factory=list)
    allowed_directories: List[str] = Field(default_factory=lambda: [
        "/testbed", "/tmp/agent"
    ])
    max_execution_time_seconds: int = 30
    max_memory_mb: int = 512

    @classmethod
    def load_config(cls, path: str) -> "SandboxConfig":
        """Load sandbox configuration from a JSON file."""
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if hasattr(cls, "model_validate"):
            return cls.model_validate(data)
        return cls.parse_obj(data)
