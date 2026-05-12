import multiprocessing
import signal
import time
from typing import Any, Dict, TYPE_CHECKING

from sandbox.core.SandboxResult import SandboxResult
from sandbox.runtime.SandboxWorker import SandboxWorker

if TYPE_CHECKING:
    from sandbox.core.Sandbox import Sandbox


class SandboxSession:
    """Persistent sandbox session that keeps globals across executions."""

    def __init__(self, sandbox: "Sandbox") -> None:
        """Create a persistent sandbox session.

        Args:
            sandbox (Sandbox): Owning sandbox instance.
        """
        self._sandbox = sandbox
        self._sandbox._refresh_tools()

        ctx = multiprocessing.get_context("spawn")
        self._control_parent, control_child = ctx.Pipe()
        self._tool_parent, tool_child = ctx.Pipe()

        if hasattr(self._sandbox.config, "model_dump"):
            config_data = self._sandbox.config.model_dump()
        else:
            config_data = self._sandbox.config.dict()

        tools = (
            list(self._sandbox._tools)
            if self._sandbox.mcp_client is not None
            else []
        )
        self._process = ctx.Process(
            target=SandboxWorker.run_loop,
            args=(control_child, tool_child, tools, config_data),
        )
        self._process.start()

    def execute(self, code: str) -> SandboxResult:
        """Execute code inside the persistent worker process.

        Args:
            code (str): Python source code to execute.

        Returns:
            SandboxResult: Execution result.
        """
        if not self._process.is_alive():
            return SandboxResult(
                stdout="",
                stderr="",
                error="Sandbox session is not running",
                final_answer=None,
                timed_out=False,
                exit_code=self._process.exitcode,
            )

        try:
            self._control_parent.send({"type": "exec", "code": code})
        except (BrokenPipeError, EOFError):
            if self._process.exitcode == -signal.SIGINT:
                raise KeyboardInterrupt()
            if self._process.exitcode == -signal.SIGTERM:
                raise SystemExit()
            return SandboxResult(
                stdout="",
                stderr="",
                error="Sandbox session is not running",
                final_answer=None,
                timed_out=False,
                exit_code=self._process.exitcode,
            )
        start_time = time.monotonic()
        timed_out = False

        result_data: Dict[str, Any] = {}
        while True:
            if (
                self._sandbox.mcp_client is not None
                and self._tool_parent.poll(0.05)
            ):
                try:
                    message = self._tool_parent.recv()
                except EOFError:
                    if self._process.exitcode == -signal.SIGINT:
                        raise KeyboardInterrupt()
                    if self._process.exitcode == -signal.SIGTERM:
                        raise SystemExit()
                    timed_out = True
                    self._process.terminate()
                    break
                if message.get("type") == "tool_call":
                    response = self._sandbox._handle_tool_call(message)
                    self._tool_parent.send(response)
            if self._control_parent.poll(0.05):
                try:
                    result_data = self._control_parent.recv()
                except EOFError:
                    if self._process.exitcode == -signal.SIGINT:
                        raise KeyboardInterrupt()
                    if self._process.exitcode == -signal.SIGTERM:
                        raise SystemExit()
                    # Worker died (e.g. RLIMIT_CPU SIGXCPU, MemoryError on
                    # send, etc.) — treat as a timeout/OOM rather than crash.
                    timed_out = True
                    self._process.terminate()
                    break
                break
            if (
                time.monotonic() - start_time
                > self._sandbox.config.max_execution_time_seconds
            ):
                timed_out = True
                self._process.terminate()
                break
            if not self._process.is_alive():
                # Worker exited without sending a result (killed by RLIMIT_*
                # or crashed). Surface as a timeout for the caller.
                timed_out = True
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

    def is_alive(self) -> bool:
        """Return whether the worker process is alive.

        Returns:
            bool: True if the process is alive.
        """
        return self._process.is_alive()

    def close(self) -> None:
        """Close the worker process and cleanup resources."""
        if not self._process.is_alive():
            return
        try:
            self._control_parent.send({"type": "close"})
            self._process.join(timeout=0.5)
        finally:
            if self._process.is_alive():
                self._process.terminate()
