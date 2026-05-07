import builtins
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List

from sandbox.config.SandboxConfig import SandboxConfig
from sandbox.security.SecurityException import SecurityException


class SafeBuiltinsFactory:
    """Builds the restricted builtins dictionary for sandbox execution."""

    @staticmethod
    def build(config: SandboxConfig) -> Dict[str, Any]:
        _ = config
        return {
            "print": builtins.print,
        }

    @staticmethod
    def safe_open_factory(config: SandboxConfig) -> Callable[..., Any]:
        allowed_dirs = SafeBuiltinsFactory.resolve_allowed_directories(config.allowed_directories)

        def safe_open(file: str, *args: Any, **kwargs: Any) -> Any:
            candidate = Path(file)
            if not candidate.is_absolute():
                candidate = Path.cwd() / candidate
            if not SafeBuiltinsFactory.is_path_allowed(candidate, allowed_dirs):
                raise SecurityException(f"File access denied: {candidate}")
            return open(candidate, *args, **kwargs)

        return safe_open

    @staticmethod
    def safe_import_factory(config: SandboxConfig) -> Callable[..., Any]:
        def safe_import(
            name: str,
            globals_: Any = None,
            locals_: Any = None,
            fromlist: Any = (),
            level: int = 0,
        ) -> Any:
            if level and level > 0:
                raise SecurityException("Relative imports are not allowed")
            raise SecurityException(f"Import not allowed: {name}")

        return safe_import

    @staticmethod
    def resolve_allowed_directories(allowed: Iterable[str]) -> List[Path]:
        return [Path(path).resolve() for path in allowed]

    @staticmethod
    def is_path_allowed(path: Path, allowed_dirs: Iterable[Path]) -> bool:
        resolved = path.resolve()
        for allowed_dir in allowed_dirs:
            if resolved.is_relative_to(allowed_dir):
                return True
        return False
