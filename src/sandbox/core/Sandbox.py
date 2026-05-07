import multiprocessing
import time
from typing import Any, Dict, Optional, TYPE_CHECKING

from sandbox.config.SandboxConfig import SandboxConfig
from sandbox.security.SecurityException import SecurityException
from sandbox.security.ImportAllowlistValidator import ImportAllowlistValidator
from sandbox.security.AllowedAttributeBases import AllowedAttributeBases
from sandbox.tools.ToolRegistry import ToolRegistry
from sandbox.runtime.SandboxWorker import SandboxWorker
from sandbox.core.SandboxResult import SandboxResult

if TYPE_CHECKING:
    from sandbox.core.SandboxSession import SandboxSession


class Sandbox:
    """Secure sandbox that executes code in an isolated process."""

    def __init__(self, config: Optional[SandboxConfig] = None, mcp_client: Any = None) -> None:
        self.config = config or SandboxConfig()
        self.mcp_client = mcp_client
        self._tools = ToolRegistry.extract_tools_schema(mcp_client)

    def _refresh_tools(self) -> None:
        self._tools = ToolRegistry.extract_tools_schema(self.mcp_client)

    def generate_manual(self) -> str:
        self._refresh_tools()
        return ToolRegistry.build_manual(self._tools)

    def execute(self, code: str) -> SandboxResult:
        allowed_calls = {"print", "final_answer", "generate_manual"}
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

        ctx = multiprocessing.get_context("spawn")
        result_queue: multiprocessing.Queue = ctx.Queue()
        parent_pipe, child_pipe = ctx.Pipe()

        self._refresh_tools()
        tools = list(self._tools) if self.mcp_client is not None else []

        if hasattr(self.config, "model_dump"):
            config_data = self.config.model_dump()
        else:
            config_data = self.config.dict()

        process = ctx.Process(
            target=SandboxWorker.run_once,
            args=(code, config_data, tools, child_pipe, result_queue),
        )
        process.start()

        start_time = time.monotonic()
        timed_out = False

        while process.is_alive():
            if self.mcp_client is not None and parent_pipe.poll(0.05):
                message = parent_pipe.recv()
                if message.get("type") == "tool_call":
                    response = self._handle_tool_call(message)
                    parent_pipe.send(response)
            if time.monotonic() - start_time > self.config.max_execution_time_seconds:
                timed_out = True
                process.terminate()
                break
            process.join(timeout=0.05)

        process.join(timeout=0.1)

        result_data: Dict[str, Any] = {}
        try:
            result_data = result_queue.get_nowait()
        except Exception:
            result_data = {
                "stdout": "",
                "stderr": "",
                "error": "No result returned from sandbox",
                "final_answer": None,
                "timed_out": timed_out,
            }

        if timed_out and not result_data.get("error"):
            result_data["error"] = "Execution timed out"

        interrupt_type = result_data.get("interrupt")
        if interrupt_type == "KeyboardInterrupt":
            raise KeyboardInterrupt()
        if interrupt_type == "SystemExit":
            raise SystemExit()

        return SandboxResult(
            stdout=result_data.get("stdout", ""),
            stderr=result_data.get("stderr", ""),
            error=result_data.get("error"),
            final_answer=result_data.get("final_answer"),
            timed_out=timed_out or result_data.get("timed_out", False),
            exit_code=process.exitcode,
        )

    def start_session(self) -> "SandboxSession":
        from sandbox.core.SandboxSession import SandboxSession

        return SandboxSession(self)

    def _handle_tool_call(self, message: Dict[str, Any]) -> Dict[str, Any]:
        name = message.get("name")
        arguments = message.get("arguments") or {}
        if not self.mcp_client:
            return {"status": "error", "error": "No MCP client configured"}
        try:
            if hasattr(self.mcp_client, "call_tool") and callable(self.mcp_client.call_tool):
                result = self.mcp_client.call_tool(name, arguments)
            elif hasattr(self.mcp_client, "invoke_tool") and callable(self.mcp_client.invoke_tool):
                result = self.mcp_client.invoke_tool(name, arguments)
            else:
                raise RuntimeError("MCP client does not support tool calls")
            return {"status": "ok", "result": result}
        except Exception as exc:
            return {"status": "error", "error": f"{exc.__class__.__name__}: {exc}"}
