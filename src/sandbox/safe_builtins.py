import builtins
import importlib
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List

from .config import SandboxConfig
from .exceptions import SecurityException
from .security import ImportAllowlistValidator


def _resolve_allowed_directories(allowed: Iterable[str]) -> List[Path]:
    return [Path(path).resolve() for path in allowed]


def _is_path_allowed(path: Path, allowed_dirs: Iterable[Path]) -> bool:
    resolved = path.resolve()
    for allowed_dir in allowed_dirs:
        if resolved.is_relative_to(allowed_dir):
            return True
    return False


def _safe_open_factory(config: SandboxConfig) -> Callable[..., Any]:
    allowed_dirs = _resolve_allowed_directories(config.allowed_directories)

    def safe_open(file: str, *args: Any, **kwargs: Any) -> Any:
        candidate = Path(file)
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        if not _is_path_allowed(candidate, allowed_dirs):
            raise SecurityException(f"File access denied: {candidate}")
        return open(candidate, *args, **kwargs)

    return safe_open


def _safe_import_factory(config: SandboxConfig) -> Callable[..., Any]:
    validator = ImportAllowlistValidator(config.authorized_imports)

    def safe_import(name: str, globals_: Any = None, locals_: Any = None, fromlist: Any = (), level: int = 0) -> Any:
        if level and level > 0:
            raise SecurityException("Relative imports are not allowed")
        if not validator._is_allowed_import(name):
            raise SecurityException(f"Import not allowed: {name}")
        return importlib.import_module(name)

    return safe_import


def _build_safe_builtins(config: SandboxConfig) -> Dict[str, Any]:
    """Return a minimal builtins map to deny all builtins by default."""
    _ = config
    return {
        "print": builtins.print,
    }
