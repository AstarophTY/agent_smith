import argparse
import importlib.util
import inspect
import subprocess
import sys
from types import ModuleType
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

from sandbox import Sandbox, SandboxConfig
from mcp_sys.containerizer import Containerizer


def launch_mcp_server_subprocess(
    tools_module: str,
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8000,
) -> subprocess.Popen[bytes]:
    """Launch mcp_server as a subprocess with the given tools module."""
    cmd = [
        "uv",
        "run",
        "mcp_server",
        "--transport",
        transport,
        "--tools-module",
        tools_module,
    ]
    if transport == "http":
        cmd.extend(["--host", host, "--port", str(port)])

    print(f"Launching MCP server (subprocess): {' '.join(cmd)}")
    return subprocess.Popen(cmd)


def run_mcp_server_stdio(tools_module: str) -> None:
    """Run mcp_server in foreground for stdio transport."""
    cmd = [
        "uv",
        "run",
        "mcp_server",
        "--transport",
        "stdio",
        "--tools-module",
        tools_module,
    ]
    print(f"Launching MCP server (foreground stdio): {' '.join(cmd)}")
    subprocess.run(cmd, check=False)


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Secure sandbox CLI")
    parser.add_argument(
        "config",
        nargs="?",
        help="Path to sandbox config JSON"
    )
    parser.add_argument(
        "--mcp-stdio",
        dest="mcp_stdio",
        help="Command for MCP stdio tools (e.g., 'python mcp_tools_mbpp.py')",
    )
    parser.add_argument(
        "--mcp-server",
        dest="mcp_server",
        help="URL for MCP server (HTTP transport)",
    )
    return parser.parse_args(argv)


class LocalToolsClient:
    """Local MCP-like client that dispatches to functions in a tools module."""

    def __init__(
        self,
        module: ModuleType,
        containerizer: Optional[Containerizer] = None
    ) -> None:
        self._tools: Dict[str, Callable[..., Any]] = {}
        self._schemas: list[dict[str, Any]] = []
        self.containerizer = containerizer
        self._load_tools(module)

    def _load_tools(self, module: ModuleType) -> None:
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            attr = getattr(module, attr_name)
            if isinstance(attr, type):
                try:
                    # Inject containerizer if the class accepts it
                    sig = inspect.signature(attr)
                    if "containerizer" in sig.parameters:
                        instance = attr(containerizer=self.containerizer)
                    else:
                        instance = attr()
                except Exception:
                    instance = attr
                self._register_instance(instance)
            elif callable(attr):
                self._register_tool(attr)

    def _register_instance(self, instance: Any) -> None:
        for method_name in dir(instance):
            if method_name.startswith("_"):
                continue
            method = getattr(instance, method_name)
            if callable(method):
                self._register_tool(method, name_override=method_name)

    def _register_tool(
        self,
        func: Callable[..., Any],
        name_override: Optional[str] = None,
    ) -> None:
        name = name_override or getattr(func, "__name__", "tool")
        assert isinstance(name, str)
        self._tools[name] = func
        self._schemas.append(self._build_schema(name, func))

    def _build_schema(
        self,
        name: str,
        func: Callable[..., Any]
    ) -> dict[str, Any]:
        signature = inspect.signature(func)
        properties: Dict[str, Any] = {}
        for param in signature.parameters.values():
            if param.name == "self":
                continue
            properties[param.name] = {"type": "string"}
        description = (
            (func.__doc__ or "").strip().splitlines()[0]
            if func.__doc__
            else ""
        )
        return {
            "name": name,
            "description": description,
            "inputSchema": {"type": "object", "properties": properties},
        }

    def list_tools(self) -> list[dict[str, Any]]:
        return list(self._schemas)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if name not in self._tools:
            raise RuntimeError(f"Unknown tool: {name}")
        return self._tools[name](**arguments)


def load_tools_module(path: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location("tools_module", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"Unable to load tools module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_interactive(sandbox: Sandbox) -> None:
    print(
        "Interactive sandbox. End a block with an empty line. "
        "Type 'exit' to quit."
    )
    buffer: list[str] = []
    while True:
        prompt = ">>> " if not buffer else "... "
        try:
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            break
        except UnicodeDecodeError as exc:
            print(
                f"\033[31mUnicodeDecodeError: {exc}\033[0m",
                file=sys.stderr,
            )
            buffer = []
            continue
        if not buffer and line.strip().lower() in {"exit", "quit"}:
            break
        if line.strip() == "":
            code = "\n".join(buffer).strip()
            buffer = []
            if not code:
                continue
            try:
                result = sandbox.execute(code)
            except KeyboardInterrupt:
                print()
                break
            except Exception as exc:
                print(
                    f"\033[31m{exc.__class__.__name__}: {exc}\033[0m",
                    file=sys.stderr,
                )
                continue
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="", file=sys.stderr)
            if result.error:
                print(
                    f"\033[31m{result.error}\033[0m",
                    file=sys.stderr,
                )
            if result.final_answer is not None:
                print(f"Final answer: {result.final_answer}")
            continue
        buffer.append(line)


def main(argv: Optional[list[str]] = None) -> None:
    args = _parse_args(argv)

    try:
        config = SandboxConfig.load_config(args.config) if args.config else None
    except Exception as e:
        print(f"Error loading sandbox config: {e}", file=sys.stderr)
        sys.exit(1)

    mcp_client = None
    try:
        sandbox = Sandbox(config=config)
    except Exception as e:
        print(f"Error initializing sandbox: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        if not args.config and not args.mcp_stdio and not args.mcp_server:
            _run_interactive(sandbox)
            return

        if args.mcp_server:
            parsed = urlparse(args.mcp_server)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 8000
            try:
                launch_mcp_server_subprocess(
                    tools_module="mcp_tools_mbpp.py",
                    transport="http",
                    host=host,
                    port=port,
                )
            except Exception as e:
                print(f"Error launching MCP server: {e}", file=sys.stderr)
                sys.exit(1)

            print("MCP server launched (HTTP mode)")
            print(
                "HTTP MCP client is not configured; sandbox will run without "
                "remote tools."
            )
            _run_interactive(sandbox)
            return

        if args.mcp_stdio:
            from logger.classes.Logger import Logger
            try:
                Logger.setup("sandbox", "mcp-stdio")
            except Exception:
                pass

            try:
                tools_module = args.mcp_stdio.replace("python ", "").strip()
                module = load_tools_module(tools_module)
            except Exception as e:
                print(f"Error loading tools module: {e}", file=sys.stderr)
                sys.exit(1)

            containerizer = Containerizer()
            try:
                containerizer.up()
                try:
                    mcp_client = LocalToolsClient(module, containerizer=containerizer)
                    sandbox = Sandbox(config=config, mcp_client=mcp_client)
                    _run_interactive(sandbox)
                finally:
                    containerizer.down()
            except Exception as e:
                print(f"Error in containerizer or sandbox execution: {e}", file=sys.stderr)
                sys.exit(1)
            return

        if args.config:
            _run_interactive(sandbox)
    finally:
        try:
            sandbox.close()
        except Exception:
            pass


app = main
