from typing import Any, Dict, Optional

from sandbox.config.SandboxConfig import SandboxConfig
from sandbox.security.SecurityException import SecurityException
from sandbox.security.ImportAllowlistValidator import ImportAllowlistValidator
from sandbox.security.AllowedAttributeBases import AllowedAttributeBases
from sandbox.tools.ToolRegistry import ToolRegistry
from sandbox.core.SandboxResult import SandboxResult
from sandbox.core.SandboxSession import SandboxSession


class Sandbox:
    """Secure sandbox that executes code in an isolated process."""

    def __init__(
        self,
        config: Optional[SandboxConfig] = None,
        mcp_client: Any = None
    ) -> None:
        """Initialize a sandbox instance.

        Args:
            config (Optional[SandboxConfig]): Sandbox configuration.
            mcp_client (Any): MCP client instance or None.
        """
        self.config = config or SandboxConfig()
        self.mcp_client = mcp_client
        self._tools = ToolRegistry.extract_tools_schema(mcp_client)
        self._session: Optional[SandboxSession] = None

    def _refresh_tools(self) -> None:
        """Refresh cached tool schemas from the MCP client."""
        self._tools = ToolRegistry.extract_tools_schema(self.mcp_client)

    def generate_manual(self) -> str:
        """Generate a human-readable tools manual.

        Returns:
            str: Manual describing available tools.
        """
        self._refresh_tools()
        manual: str = ToolRegistry.build_manual(self._tools)
        return manual

    def execute(self, code: str) -> SandboxResult:
        """Execute code in the persistent sandbox session.

        Args:
            code (str): Python source code to execute.

        Returns:
            SandboxResult: Execution result.
        """
        allowed_calls = {
            # Base
            "print",
            "input",
            "len",
            "range",
            "enumerate",
            "zip",
            "map",
            "filter",
            "sorted",
            "reversed",
            "sum",
            "min",
            "max",
            "abs",
            "round",
            "pow",
            "divmod",
            "all",
            "any",

            # Types / conversion
            "str",
            "int",
            "float",
            "bool",
            "list",
            "dict",
            "set",
            "tuple",

            # Inspection
            "type",
            "isinstance",
            "hasattr",
            "getattr",
            "setattr",
            "callable",

            # Custom agent tools
            "final_answer",
            "generate_manual",
        }
        self._refresh_tools()
        for tool in self._tools:
            name = tool.get("name")
            if name:
                allowed_calls.add(name)
        allowed_attribute_bases = AllowedAttributeBases.build(())
        validator = ImportAllowlistValidator(
            (),
            allowed_calls=allowed_calls,
            allowed_attribute_bases=allowed_attribute_bases,
        )
        try:
            validator.validate(code)
        except SecurityException as exc:
            return SandboxResult(
                stdout="",
                stderr="",
                error=f"{exc.__class__.__name__}: {exc}",
                final_answer=None,
                timed_out=False,
                exit_code=None,
            )
        if self._session is None or not self._session.is_alive():
            self._session = SandboxSession(self)
        return self._session.execute(code)

    def close(self) -> None:
        """Close the underlying sandbox session, if present."""
        if self._session is None:
            return
        self._session.close()

    def _handle_tool_call(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a tool call message from the worker process.

        Args:
            message (Dict[str, Any]): Tool call request data.

        Returns:
            Dict[str, Any]: Tool call response data.
        """
        name = message.get("name")
        arguments = message.get("arguments") or {}
        if not self.mcp_client:
            return {"status": "error", "error": "No MCP client configured"}
        try:
            if hasattr(self.mcp_client, "call_tool") and callable(
                self.mcp_client.call_tool
            ):
                result = self.mcp_client.call_tool(name, arguments)
            elif hasattr(self.mcp_client, "invoke_tool") and callable(
                self.mcp_client.invoke_tool
            ):
                result = self.mcp_client.invoke_tool(name, arguments)
            else:
                raise RuntimeError("MCP client does not support tool calls")
            return {"status": "ok", "result": result}
        except Exception as exc:
            return {
                "status": "error",
                "error": f"{exc.__class__.__name__}: {exc}",
            }
