import contextlib
import io
import multiprocessing
from typing import Any, Dict, List, Optional

from multiprocessing.connection import Connection

from .config import SandboxConfig
from .exceptions import FinalAnswerSignal
from .safe_builtins import _build_safe_builtins
from .security import ImportAllowlistValidator, build_allowed_attribute_bases
from .tools import _build_manual, _make_tool_function


def _sandbox_worker(
    code: str,
    config_data: Dict[str, Any],
    tools: List[Dict[str, Any]],
    tool_pipe: Connection,
    result_queue: multiprocessing.Queue,
) -> None:
    config = SandboxConfig(**config_data)
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    allowed_calls = {"print", "final_answer", "generate_manual"}
    allowed_attribute_bases = build_allowed_attribute_bases(config.authorized_imports)
    validator = ImportAllowlistValidator(
        config.authorized_imports,
        allowed_calls=allowed_calls,
        allowed_attribute_bases=allowed_attribute_bases,
    )

    final_answer_value: Optional[str] = None

    def final_answer(answer_string: str) -> None:
        nonlocal final_answer_value
        final_answer_value = str(answer_string)
        raise FinalAnswerSignal()

    safe_builtins = _build_safe_builtins(config)
    globals_dict: Dict[str, Any] = {"__builtins__": safe_builtins, "__name__": "__sandbox__"}
    globals_dict["final_answer"] = final_answer
    globals_dict["generate_manual"] = lambda: _build_manual(tools)

    for tool in tools:
        name = tool.get("name")
        if name:
            input_schema = tool.get("inputSchema") or tool.get("input_schema") or {}
            properties = input_schema.get("properties", {}) if isinstance(input_schema, dict) else {}
            param_order = list(properties.keys()) if isinstance(properties, dict) else []
            globals_dict[name] = _make_tool_function(name, tool_pipe, param_order)
            validator.allowed_calls.add(name)

    try:
        validator.validate(code)
        with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
            import resource
            max_bytes = config.max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))
            resource.setrlimit(resource.RLIMIT_CPU, (config.max_execution_time_seconds, config.max_execution_time_seconds))
            exec(compile(code, "<sandbox>", "exec"), globals_dict, None)
        result_queue.put({
            "stdout": stdout_buffer.getvalue(),
            "stderr": stderr_buffer.getvalue(),
            "error": None,
            "final_answer": final_answer_value,
            "timed_out": False,
        })
    except FinalAnswerSignal:
        result_queue.put({
            "stdout": stdout_buffer.getvalue(),
            "stderr": stderr_buffer.getvalue(),
            "error": None,
            "final_answer": final_answer_value,
            "timed_out": False,
        })
    except (KeyboardInterrupt, SystemExit) as exc:
        result_queue.put({
            "stdout": stdout_buffer.getvalue(),
            "stderr": stderr_buffer.getvalue(),
            "error": f"{exc.__class__.__name__}: {exc}",
            "final_answer": final_answer_value,
            "timed_out": False,
            "interrupt": exc.__class__.__name__,
        })
        raise
    except Exception as exc:
        result_queue.put({
            "stdout": stdout_buffer.getvalue(),
            "stderr": stderr_buffer.getvalue(),
            "error": f"{exc.__class__.__name__}: {exc}",
            "final_answer": final_answer_value,
            "timed_out": False,
        })


def _sandbox_worker_loop(
    control_pipe: Connection,
    tool_pipe: Connection,
    tools: List[Dict[str, Any]],
    config_data: Dict[str, Any],
) -> None:
    config = SandboxConfig(**config_data)
    allowed_calls = {"print", "final_answer", "generate_manual"}
    allowed_attribute_bases = build_allowed_attribute_bases(config.authorized_imports)
    validator = ImportAllowlistValidator(
        config.authorized_imports,
        allowed_calls=allowed_calls,
        allowed_attribute_bases=allowed_attribute_bases,
    )

    safe_builtins = _build_safe_builtins(config)
    globals_dict: Dict[str, Any] = {"__builtins__": safe_builtins, "__name__": "__sandbox__"}
    globals_dict["generate_manual"] = lambda: _build_manual(tools)

    for tool in tools:
        name = tool.get("name")
        if name:
            input_schema = tool.get("inputSchema") or tool.get("input_schema") or {}
            properties = input_schema.get("properties", {}) if isinstance(input_schema, dict) else {}
            param_order = list(properties.keys()) if isinstance(properties, dict) else []
            globals_dict[name] = _make_tool_function(name, tool_pipe, param_order)
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
            with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
                import resource
                max_bytes = config.max_memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))
                resource.setrlimit(resource.RLIMIT_CPU, (config.max_execution_time_seconds, config.max_execution_time_seconds))
                exec(compile(code, "<sandbox>", "exec"), globals_dict, None)
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
