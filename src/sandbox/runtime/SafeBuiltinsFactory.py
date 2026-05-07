import builtins
from typing import Any, Dict

from sandbox.config.SandboxConfig import SandboxConfig


class SafeBuiltinsFactory:
    """Builds the restricted builtins dictionary for sandbox execution."""

    @staticmethod
    def build(config: SandboxConfig) -> Dict[str, Any]:
        _ = config
        return {
            "print": builtins.print,
        }
