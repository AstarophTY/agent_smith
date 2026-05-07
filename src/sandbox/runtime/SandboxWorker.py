import contextlib
import io
from typing import Any, Dict, List, Optional

from multiprocessing.connection import Connection

from sandbox.config.SandboxConfig import SandboxConfig
from sandbox.runtime.FinalAnswerSignal import FinalAnswerSignal
from sandbox.runtime.SafeBuiltinsFactory import SafeBuiltinsFactory
from sandbox.security.ImportAllowlistValidator import ImportAllowlistValidator
from sandbox.security.AllowedAttributeBases import AllowedAttributeBases
from sandbox.tools.ToolRegistry import ToolRegistry


class SandboxWorker:
    """Executes sandbox code in a persistent worker loop."""

    @staticmethod
    def run_loop(
        control_pipe: Connection,
        tool_pipe: Connection,
        tools: List[Dict[str, Any]],
        config_data: Dict[str, Any],
    ) -> None:
        """Run the persistent execution loop inside the worker process.

        Args:
            control_pipe (Connection): Pipe for exec requests and results.
            tool_pipe (Connection): Pipe for tool call requests and responses.
            tools (List[Dict[str, Any]]): Tool schema list for MCP wrappers.
            config_data (Dict[str, Any]): Serialized sandbox configuration.
        """
        config = SandboxConfig(**config_data)
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
        allowed_attribute_bases = AllowedAttributeBases.build(())
        validator = ImportAllowlistValidator(
            (),
            allowed_calls=allowed_calls,
            allowed_attribute_bases=allowed_attribute_bases,
        )

        safe_builtins = SafeBuiltinsFactory.build(config)
        globals_dict: Dict[str, Any] = {
            "__builtins__": safe_builtins,
            "__name__": "__sandbox__",
        }
        globals_dict["generate_manual"] = lambda: ToolRegistry.build_manual(
            tools
        )

        for tool in tools:
            name = tool.get("name")
            if name:
                param_order = ToolRegistry.param_order_from_schema(tool)
                globals_dict[name] = ToolRegistry.make_tool_function(
                    name,
                    tool_pipe,
                    param_order,
                )
                validator.allowed_calls.add(name)

        while True:
            message = control_pipe.recv()
            if message.get("type") == "close":
                break
            if message.get("type") != "exec":
                continue

            code = message.get("code", "")
            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()
            final_answer_value: Optional[str] = None

            def final_answer(answer_string: str) -> None:
                nonlocal final_answer_value
                final_answer_value = str(answer_string)
                raise FinalAnswerSignal()

            globals_dict["final_answer"] = final_answer

            try:
                validator.validate(code)
                with (
                    contextlib.redirect_stdout(stdout_buffer),
                    contextlib.redirect_stderr(stderr_buffer),
                ):
                    import resource
                    max_bytes = config.max_memory_mb * 1024 * 1024
                    resource.setrlimit(
                        resource.RLIMIT_AS, (max_bytes, max_bytes)
                    )
                    resource.setrlimit(
                        resource.RLIMIT_CPU,
                        (
                            config.max_execution_time_seconds,
                            config.max_execution_time_seconds,
                        ),
                    )
                    exec(
                        compile(code, "<sandbox>", "exec"), globals_dict,
                        None
                    )
                control_pipe.send({
                    "stdout": stdout_buffer.getvalue(),
                    "stderr": stderr_buffer.getvalue(),
                    "error": None,
                    "final_answer": final_answer_value,
                    "timed_out": False,
                })
            except FinalAnswerSignal:
                control_pipe.send({
                    "stdout": stdout_buffer.getvalue(),
                    "stderr": stderr_buffer.getvalue(),
                    "error": None,
                    "final_answer": final_answer_value,
                    "timed_out": False,
                })
            except (KeyboardInterrupt, SystemExit) as exc:
                control_pipe.send({
                    "stdout": stdout_buffer.getvalue(),
                    "stderr": stderr_buffer.getvalue(),
                    "error": f"{exc.__class__.__name__}: {exc}",
                    "final_answer": final_answer_value,
                    "timed_out": False,
                    "interrupt": exc.__class__.__name__,
                })
                raise
            except Exception as exc:
                control_pipe.send({
                    "stdout": stdout_buffer.getvalue(),
                    "stderr": stderr_buffer.getvalue(),
                    "error": f"{exc.__class__.__name__}: {exc}",
                    "final_answer": final_answer_value,
                    "timed_out": False,
                })
