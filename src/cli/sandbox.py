import typer
import subprocess
from typing import Optional
from urllib.parse import urlparse


app = typer.Typer()


def launch_mcp_server_subprocess(
    tools_module: str,
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8000
) -> subprocess.Popen:
    """Launch mcp_server as a subprocess with the given tools module."""
    cmd = [
        "uv", "run", "mcp_server",
        "--transport", transport,
        "--tools-module", tools_module,
    ]
    if transport == "http":
        cmd.extend(["--host", host, "--port", str(port)])

    print(f"Launching MCP server (subprocess): {' '.join(cmd)}")
    return subprocess.Popen(cmd)


def run_mcp_server_stdio(tools_module: str) -> None:
    """Run mcp_server in foreground for stdio transport."""
    cmd = [
        "uv", "run", "mcp_server",
        "--transport", "stdio",
        "--tools-module", tools_module,
    ]
    print(f"Launching MCP server (foreground stdio): {' '.join(cmd)}")
    subprocess.run(cmd, check=False)


@app.callback(invoke_without_command=True)
def main(
        ctx: typer.Context,
        template: Optional[str] = typer.Argument(
            None,
            help="Path to the configuration template"
        ),
        mcp_stdio: Optional[str] = typer.Option(
            None,
            "--mcp-stdio",
            help="Command for MCP stdio tools"
        ),
        mcp_server: Optional[str] = typer.Option(
            None,
            "--mcp-server",
            help="URL for MCP server"
        )
) -> None:
    """
    Sandbox CLI dispatcher for tools A, B, C, D, and E.
    """
    if ctx.invoked_subcommand is not None:
        return

    # A: Launch interactive sandbox (fake)
    if not template and not mcp_stdio and not mcp_server:
        print("Launching interactive sandbox (fake)")

    # D: With MBPP tools (HTTP) - launch MCP server with URL
    elif mcp_server:
        print(f"Connecting to MCP server at {mcp_server} (fake for sandbox)")
        parsed = urlparse(mcp_server)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 8000
        # Launch MCP server as subprocess
        print("Launching MCP server subprocess for HTTP transport")
        launch_mcp_server_subprocess(
            tools_module="mcp_tools_mbpp.py",
            transport="http",
            host=host,
            port=port
        )
        print("MCP server launched (HTTP mode)")

    # Scenarios involving a template file
    elif template:
        # B: With custom configuration (fake)
        if not mcp_stdio:
            print(f"Launching sandbox with template {template} (fake)")

        # C: With MBPP tools (stdio)
        elif mcp_stdio and "mbpp" in mcp_stdio:
            print("Launching sandbox with MBPP tools (stdio)")
            # Extract tools module path from command
            tools_module = mcp_stdio.replace("python ", "").strip()
            run_mcp_server_stdio(tools_module=tools_module)

        # E: With SWE-bench tools
        elif mcp_stdio and "swebench" in mcp_stdio:
            print("Launching sandbox with SWE-bench tools (stdio)")
            # Extract tools module path from command
            tools_module = mcp_stdio.replace("python ", "").strip()
            run_mcp_server_stdio(tools_module=tools_module)
