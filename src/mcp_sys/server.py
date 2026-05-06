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
) -> None:
    MCPServer(
        host=host,
        port=port,
        http_path=http_path,
    ).run(transport=transport)
