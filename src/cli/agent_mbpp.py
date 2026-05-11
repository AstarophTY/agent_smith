import asyncio
import json
import os
import sys

import typer
from dotenv import load_dotenv

from agenticloop.classes.AgenticLoop import AgenticLoop, AgenticLoopResult
from cli.sandbox import load_tools_module
from logger.classes.Logger import Logger
from models.MBPPTaskInput import MBPPTaskInput
from models.SolutionOutput import SolutionOutput
from models.StepMetrics import StepMetrics

app = typer.Typer()


def _build_solution(
    task: MBPPTaskInput,
    result: AgenticLoopResult,
) -> SolutionOutput:
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
        task_id=str(task.task_id),
        benchmark="mbpp",
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
    task: MBPPTaskInput,
    model_name: str,
    provider_url: str,
) -> AgenticLoopResult:
    async with AgenticLoop(
        max_iterations=10,
        tool_module=load_tools_module("mcp_tools_mbpp.py"),
        model_name=model_name,
        provider_url=provider_url,
    ) as loop:
        return await loop.run(task=task)


@app.callback(invoke_without_command=True)
@app.command()
def main(
    task_file: str = typer.Option(
        ..., "--task-file", help="Path to the task JSON file"
    ),
    output: str = typer.Option(
        ..., "--output", help="Path to the output JSON file"
    ),
    model_name: str = typer.Option(
        ..., "--model-name", help="LLM model identifier"
    ),
    provider_url: str = typer.Option(
        ..., "--provider-url", help="LLM API base URL"
    ),
) -> None:
    """Run the MBPP agent on a single task."""
    load_dotenv()

    with open(task_file, "r", encoding="utf-8") as fh:
        task = MBPPTaskInput.model_validate(json.load(fh))

    task_id_str = str(task.task_id)
    try:
        Logger.setup("mbpp", task_id_str)
    except Exception:
        pass

    os.environ["LLM_MODEL"] = model_name
    os.environ["LLM_BASE_URL"] = provider_url

    try:
        result = asyncio.run(_run(task, model_name, provider_url))
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        sys.exit(1)

    solution = _build_solution(task, result)

    with open(output, "w", encoding="utf-8") as fh:
        fh.write(solution.model_dump_json(indent=2))
        fh.write("\n")

    status = "SUCCESS" if solution.success else "FAILED"
    Logger.info(
        f"Task {task_id_str} {status} — "
        f"{solution.iterations} iters, "
        f"{solution.total_input_tokens} in / "
        f"{solution.total_output_tokens} out tokens"
    )
