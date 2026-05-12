from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Optional, TYPE_CHECKING

import typer
from dotenv import load_dotenv

if TYPE_CHECKING:
    from agenticloop.classes.AgenticLoop import AgenticLoopResult
    from models.SWEBenchTaskInput import SWEBenchTaskInput
    from models.SolutionOutput import SolutionOutput

app = typer.Typer()


def _build_solution(
    task: SWEBenchTaskInput,
    result: AgenticLoopResult,
) -> SolutionOutput:
    from models.SolutionOutput import SolutionOutput
    from models.StepMetrics import StepMetrics

    steps = [
        StepMetrics(
            step=s.step,
            input_tokens=s.input_tokens,
            output_tokens=s.output_tokens,
            request_time_ms=s.request_time_ms,
            api_url=s.api_url,
            model_name=s.model_name,
            llm_output=s.llm_output,
            sandbox_input=s.sandbox_input,
            sandbox_output=s.sandbox_output,
            retries=s.retries,
            timestamp=s.timestamp,
        )
        for s in result.steps
    ]
    return SolutionOutput(
        task_id=task.instance_id,
        benchmark="swebench",
        success=result.success,
        solution=result.final_answer or "",
        system_prompt=result.system_prompt,
        iterations=result.iterations,
        total_requests=result.total_requests,
        total_input_tokens=result.total_input_tokens,
        total_output_tokens=result.total_output_tokens,
        total_time_seconds=result.total_time_seconds,
        steps=steps,
        error=result.error_message,
    )


async def _run(
    task: SWEBenchTaskInput,
    model_name: Optional[str],
    provider_url: Optional[str],
    sandbox_config_path: Optional[str] = None,
) -> AgenticLoopResult:
    from agenticloop.classes.AgenticLoop import AgenticLoop
    from cli.sandbox import load_tools_module
    from models import SandboxConfig

    config = None
    if sandbox_config_path and os.path.exists(sandbox_config_path):
        config = SandboxConfig.load_config(sandbox_config_path)

    async with AgenticLoop(
        max_iterations=30,
        tool_module=load_tools_module("mcp_tools_swebench.py"),
        docker_image=task.docker_image,
        model_name=model_name,
        provider_url=provider_url,
        sandbox_config=config,
    ) as loop:
        return await loop.run(task=task)


@app.callback(invoke_without_command=True)
def main(
    task_file: str = typer.Option(
        ..., "--task-file", help="Path to the task JSON file"
    ),
    output: str = typer.Option(
        ..., "--output", help="Path to the output JSON file"
    ),
    model_name: Optional[str] = typer.Option(
        None,
        "--model-name",
        help="LLM model identifier (defaults to LLM_MODEL env)",
    ),
    provider_url: Optional[str] = typer.Option(
        None,
        "--provider-url",
        help="LLM API base URL (defaults to LLM_BASE_URL env)",
    ),
    sandbox_config: Optional[str] = typer.Option(
        "sandbox_template.json",
        "--sandbox-config",
        help="Path to the sandbox config JSON file",
    ),
) -> None:
    """Run the SWE-bench agent on a single task."""
    load_dotenv()

    from logger.classes.Logger import Logger
    from models.SWEBenchTaskInput import SWEBenchTaskInput

    try:
        with open(task_file, "r", encoding="utf-8") as fh:
            task = SWEBenchTaskInput.model_validate(json.load(fh))
    except Exception as e:
        print(f"Error loading task file {task_file}: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        Logger.setup("swebench", task.instance_id)
    except Exception:
        pass

    model_name = model_name or os.getenv("LLM_MODEL")
    provider_url = provider_url or os.getenv("LLM_BASE_URL")
    if not model_name or not provider_url:
        print(
            "Error: --model-name/--provider-url not given and "
            "LLM_MODEL/LLM_BASE_URL not set in environment",
            file=sys.stderr,
        )
        sys.exit(2)

    os.environ["LLM_MODEL"] = model_name
    os.environ["LLM_BASE_URL"] = provider_url

    try:
        result = asyncio.run(
            _run(task, model_name, provider_url, sandbox_config)
        )
    except (KeyboardInterrupt, SystemExit):
        print("Interrupted", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        Logger.error(f"Error running SWE-bench agent: {e}")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        solution = _build_solution(task, result)

        with open(output, "w", encoding="utf-8") as fh:
            fh.write(solution.model_dump_json(indent=2))
            fh.write("\n")

        status = "SUCCESS" if solution.success else "FAILED"
        Logger.info(
            f"Task {task.instance_id} {status} — "
            f"{solution.iterations} iters, "
            f"{solution.total_input_tokens} in / "
            f"{solution.total_output_tokens} out tokens"
        )
    except Exception as e:
        Logger.error(f"Error saving solution: {e}")
        print(f"Error saving solution: {e}", file=sys.stderr)
        sys.exit(1)
