import json

import typer
import asyncio

from models.MBPPTaskInput import MBPPTaskInput
from agenticloop.classes.AgenticLoop import AgenticLoop, AgenticLoopResult
from cli.sandbox import load_tools_module

app = typer.Typer()


async def _run(task: MBPPTaskInput) -> AgenticLoopResult:
    async with AgenticLoop(
        max_iterations=10,
        tool_module=load_tools_module("mcp_tools_mbpp.py")
    ) as loop:
        result = await loop.run(
            task=task
        )
    return result


@app.callback(invoke_without_command=True)
@app.command()
def main(
    task_file: str = typer.Option(
        ...,
        "--task-file",
        help="Path to the task file"
    ),
    output: str = typer.Option(
        ...,
        "--output",
        help="Path to the output file"
    ),
    model_name: str = typer.Option(
        ...,
        "--model-name",
        help="Model name"
    ),
    provider_url: str = typer.Option(
        ...,
        "--provider-url",
        help="Provider URL"
    )
) -> None:
    """
    Run MBPP agent.
    """
    with open(task_file, "r", encoding="utf-8") as handle:
        task = MBPPTaskInput.model_validate(json.load(handle))

    result = asyncio.run(_run(task))

    payload = {
        "task_id": task.task_id,
        "success": result.success,
        "iterations": result.iterations,
        "final_answer": result.final_answer,
        "final_code": result.final_code,
        "error_message": result.error_message,
        "history": result.history,
        "model_name": model_name,
        "provider_url": provider_url,
    }

    with open(output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

