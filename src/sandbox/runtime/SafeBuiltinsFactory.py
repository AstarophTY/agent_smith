import builtins
from typing import Any, Dict

from models.SandboxConfig import SandboxConfig


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
            "input": builtins.input,
            "len": builtins.len,
            "range": builtins.range,
            "enumerate": builtins.enumerate,
            "zip": builtins.zip,
            "map": builtins.map,
            "filter": builtins.filter,
            "sorted": builtins.sorted,
            "reversed": builtins.reversed,
            "sum": builtins.sum,
            "min": builtins.min,
            "max": builtins.max,
            "abs": builtins.abs,
            "round": builtins.round,
            "pow": builtins.pow,
            "divmod": builtins.divmod,
            "all": builtins.all,
            "any": builtins.any,

            "str": builtins.str,
            "int": builtins.int,
            "float": builtins.float,
            "bool": builtins.bool,
            "list": builtins.list,
            "dict": builtins.dict,
            "set": builtins.set,
            "tuple": builtins.tuple,

            "type": builtins.type,
            "isinstance": builtins.isinstance,
            "hasattr": builtins.hasattr,
            "getattr": builtins.getattr,
            "setattr": builtins.setattr,
            "callable": builtins.callable,
        }
