from typing import Literal

import typer

from mcp_sys.server import run_server


app = typer.Typer()


@app.callback(invoke_without_command=True)
def main(
    transport: Literal["stdio", "http"] = typer.Option(
        "stdio",
        "--transport",
        help="Transport to use. 'http' uses streamable HTTP.",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help="Host to bind in HTTP mode.",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        help="Port to bind in HTTP mode.",
    ),
    http_path: str = typer.Option(
        "/mcp",
        "--http-path",
        help="HTTP path for streamable MCP endpoint.",
    ),
) -> None:
    """
    Run MCP server in STDIO or HTTP mode.
    """
    protocol: Literal["stdio", "streamable-http"]
    if transport == "http":
        protocol = "streamable-http"
    else:
        protocol = "stdio"
    run_server(transport=protocol, host=host, port=port, http_path=http_path)
