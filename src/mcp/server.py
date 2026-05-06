import asyncio
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool


class MCPServer:
    def __init__(self) -> None:
        self.server = Server("agent-smith-tools")
        self.server.list_tools()(self.list_tools)
        self.server.call_tool()(self.call_tool)

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="print_message",
                description="Print a message to the terminal.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Message to print",
                        }
                    },
                    "required": ["message"],
                },
            )
        ]

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> list[TextContent]:
        if name != "print_message":
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        message = arguments["message"]
        return [TextContent(type="text", text=message)]

    async def run(self) -> None:
        async with stdio_server() as (read_stream, write_stream):
            initialization_options = (
                self.server.create_initialization_options()
            )
            await self.server.run(
                read_stream,
                write_stream,
                initialization_options,
            )


async def main() -> None:
    await MCPServer().run()


if __name__ == "__main__":
    asyncio.run(main())
