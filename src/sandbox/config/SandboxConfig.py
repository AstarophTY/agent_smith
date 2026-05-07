import json
from typing import List

from pydantic import BaseModel, Field


class SandboxConfig(BaseModel):
    """Configuration for the secure code execution sandbox.

    Attributes:
        allowed_directories (List[str]): Directories that can be accessed by
            safe file ops.
        max_execution_time_seconds (int): Max CPU time per execution.
        max_memory_mb (int): Max address space in megabytes.
    """
    allowed_directories: List[str] = Field(default_factory=lambda: [
        "/testbed", "/tmp/agent",
    ])
    max_execution_time_seconds: int = Field(default=30)
    max_memory_mb: int = Field(default=512)

    @classmethod
    def load_config(cls, path: str) -> "SandboxConfig":
        """Load sandbox configuration from a JSON file.

        Args:
            path (str): Path to the JSON config file.

        Returns:
            SandboxConfig: Parsed configuration instance.

        Raises:
            FileNotFoundError: If the file does not exist.
            json.JSONDecodeError: If the file is not valid JSON.
        """
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if hasattr(cls, "model_validate"):
            return cls.model_validate(data)
        return cls.parse_obj(data)
