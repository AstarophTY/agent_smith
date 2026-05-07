import multiprocessing
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .config import SandboxConfig
from .exceptions import SecurityException
from .security import ImportAllowlistValidator, build_allowed_attribute_bases
from .tools import _extract_tools_schema
from .worker import _sandbox_worker, _sandbox_worker_loop


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    error: Optional[str]
    final_answer: Optional[str]
    timed_out: bool
    exit_code: Optional[int]


class Sandbox:
    """Secure sandbox that executes code in an isolated process."""

    def __init__(self, config: Optional[SandboxConfig] = None, mcp_client: Any = None) -> None:
        self.config = config or SandboxConfig()
        self.mcp_client = mcp_client
        self._tools = _extract_tools_schema(mcp_client)

    def _refresh_tools(self) -> None:
        self._tools = _extract_tools_schema(self.mcp_client)

    def generate_manual(self) -> str:
        from .tools import _build_manual

        self._refresh_tools()
        return _build_manual(self._tools)

    def execute(self, code: str) -> SandboxResult:
        allowed_calls = {"print", "final_answer", "generate_manual"}
        self._refresh_tools()
        for tool in self._tools:
            name = tool.get("name")
            if name:
                allowed_calls.add(name)
        allowed_attribute_bases = build_allowed_attribute_bases(self.config.authorized_imports)
        validator = ImportAllowlistValidator(
            self.config.authorized_imports,
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
            target=_sandbox_worker,
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


class SandboxSession:
    """Persistent sandbox session that keeps globals across executions."""

    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox
        self._sandbox._refresh_tools()

        ctx = multiprocessing.get_context("spawn")
        self._control_parent, control_child = ctx.Pipe()
        self._tool_parent, tool_child = ctx.Pipe()

        if hasattr(self._sandbox.config, "model_dump"):
            config_data = self._sandbox.config.model_dump()
        else:
            config_data = self._sandbox.config.dict()

        tools = list(self._sandbox._tools) if self._sandbox.mcp_client is not None else []
        self._process = ctx.Process(
            target=_sandbox_worker_loop,
            args=(control_child, tool_child, tools, config_data),
        )
        self._process.start()

    def execute(self, code: str) -> SandboxResult:
        if not self._process.is_alive():
            return SandboxResult(
                stdout="",
                stderr="",
                error="Sandbox session is not running",
                final_answer=None,
                timed_out=False,
                exit_code=self._process.exitcode,
            )

        self._control_parent.send({"type": "exec", "code": code})
        start_time = time.monotonic()
        timed_out = False

        result_data: Dict[str, Any] = {}
        while True:
            if self._sandbox.mcp_client is not None and self._tool_parent.poll(0.05):
                message = self._tool_parent.recv()
                if message.get("type") == "tool_call":
                    response = self._sandbox._handle_tool_call(message)
                    self._tool_parent.send(response)
            if self._control_parent.poll(0.05):
                result_data = self._control_parent.recv()
                break
            if time.monotonic() - start_time > self._sandbox.config.max_execution_time_seconds:
                timed_out = True
                self._process.terminate()
                break

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
            exit_code=self._process.exitcode,
        )

    def close(self) -> None:
        if not self._process.is_alive():
            return
        try:
            self._control_parent.send({"type": "close"})
            self._process.join(timeout=0.5)
        finally:
            if self._process.is_alive():
                self._process.terminate()
