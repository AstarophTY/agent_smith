import typer
from typing import Optional


app = typer.Typer()


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
    TODO: Implement everything and replace the ABCDE prints
    """
    # If a specific subcommand was called (like hello/goodbye), we stop here
    if ctx.invoked_subcommand is not None:
        return

    if not template and not mcp_stdio and not mcp_server:
        print("A")

    elif mcp_server:
        print("D")

    # Scenarios involving a template file
    elif template:
        if mcp_stdio:
            if "mbpp" in mcp_stdio:
                print("C")
            elif "swebench" in mcp_stdio:
                print("E")
        else:
            print("B")
