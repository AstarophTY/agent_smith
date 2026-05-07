import builtins
from typing import Any, Dict

from sandbox.config.SandboxConfig import SandboxConfig


class SafeBuiltinsFactory:
    """Builds restricted builtins for sandbox execution."""

    @staticmethod
    def build(config: SandboxConfig) -> Dict[str, Any]:
        """Build the allowed builtins mapping.

        Args:
            config (SandboxConfig): Sandbox configuration.

        Returns:
            Dict[str, Any]: Builtins mapping exposed to sandboxed code.
        """
        _ = config
        return {
            "print": builtins.print,
        }
