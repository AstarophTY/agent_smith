from typing import Any, Callable, Dict, List

from multiprocessing.connection import Connection


def _extract_tools_schema(mcp_client: Any) -> List[Dict[str, Any]]:
    if mcp_client is None:
        return []
    if hasattr(mcp_client, "list_tools") and callable(mcp_client.list_tools):
        return list(mcp_client.list_tools())
    if hasattr(mcp_client, "tools"):
        tools = getattr(mcp_client, "tools")
        if isinstance(tools, list):
            return list(tools)
    if hasattr(mcp_client, "schema"):
        schema = mcp_client.schema
        if isinstance(schema, dict) and "tools" in schema:
            return list(schema["tools"])
    if hasattr(mcp_client, "get_schema") and callable(mcp_client.get_schema):
        schema = mcp_client.get_schema()
        if isinstance(schema, dict) and "tools" in schema:
            return list(schema["tools"])
    return []


def _build_manual(tools: List[Dict[str, Any]]) -> str:
    lines = ["Available tools:", "- final_answer(answer_string): signal completion and return a final answer"]
    for tool in tools:
        name = tool.get("name", "unknown")
        description = tool.get("description", "")
        input_schema = tool.get("inputSchema") or tool.get("input_schema") or {}
        properties = input_schema.get("properties", {}) if isinstance(input_schema, dict) else {}
        args = ", ".join(sorted(properties.keys())) if properties else ""
        arg_text = f"({args})" if args else "()"
        line = f"- {name}{arg_text}"
        if description:
            line += f": {description}"
        lines.append(line)
    return "\n".join(lines)


def _make_tool_function(
    tool_name: str,
    tool_pipe: Connection,
    param_order: List[str],
) -> Callable[..., Any]:
    def tool_function(*args: Any, **kwargs: Any) -> Any:
        if args:
            if len(args) > len(param_order):
                raise TypeError(f"Too many positional arguments for {tool_name}")
            for name, value in zip(param_order, args):
                if name in kwargs:
                    raise TypeError(f"Multiple values for argument '{name}'")
                kwargs[name] = value
        tool_pipe.send({"type": "tool_call", "name": tool_name, "arguments": kwargs})
        response = tool_pipe.recv()
        if response.get("status") == "error":
            raise RuntimeError(response.get("error", "Tool call failed"))
        return response.get("result")

    tool_function.__name__ = tool_name
    tool_function.__doc__ = f"Proxy for MCP tool '{tool_name}'."
    return tool_function
