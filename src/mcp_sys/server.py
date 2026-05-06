from typing import Literal
from fastmcp import FastMCP


class MCPServer:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        http_path: str = "/mcp",
    ) -> None:
        self.host = host
        self.port = port
        self.http_path = http_path
        self.server = FastMCP("agent-smith-tools")

    def register_tools_module(self, module_path: str) -> None:
        """Dynamically import a module and register its tools with the server."""
        import importlib.util
        import sys

        spec = importlib.util.spec_from_file_location("tools_module", module_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["tools_module"] = module
        spec.loader.exec_module(module)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type):
                try:
                    instance = attr()
                except Exception:
                    instance = attr

                for method_name in dir(instance):
                    method = getattr(instance, method_name)
                    if callable(method) and not method_name.startswith("_"):
                        try:
                            self.server.add_tool(method)
                        except Exception as e:
                            print(f"Warning: Could not register {method_name}: {e}")
            elif callable(attr) and not attr_name.startswith("_"):
                try:
                    self.server.add_tool(attr)
                except Exception as e:
                    print(f"Warning: Could not register {attr_name}: {e}")

    def run(self, transport: Literal["stdio", "streamable-http"]) -> None:
        if transport == "streamable-http":
            self.server.run(
                transport=transport,
                host=self.host,
                port=self.port,
                path=self.http_path,
            )
        else:
            self.server.run(transport=transport)


def run_server(
    transport: Literal["stdio", "streamable-http"] = "stdio",
    host: str = "127.0.0.1",
    port: int = 8000,
    http_path: str = "/mcp",
    tools_module: str | None = None,
) -> None:
    server = MCPServer(
        host=host,
        port=port,
        http_path=http_path,
    )
    if tools_module:
        server.register_tools_module(tools_module)
    server.run(transport=transport)
