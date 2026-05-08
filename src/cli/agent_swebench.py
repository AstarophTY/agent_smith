import json

import typer
import asyncio

from models.SWEBenchTaskInput import SWEBenchTaskInput
from agenticloop.classes.AgenticLoop import AgenticLoop, AgenticLoopResult
from cli.sandbox import load_tools_module

app = typer.Typer()


async def _run(task: SWEBenchTaskInput) -> AgenticLoopResult:
    async with AgenticLoop(
        max_iterations=10,
        tool_module=load_tools_module("mcp_tools_swebench.py"),
        docker_image=task.docker_image
    ) as loop:
        result = await loop.run(
            task=task
        )
    return result


@app.callback(invoke_without_command=True)
def main(
    task_file: str = typer.Option(
        ...,
        "--task-file", help="Path to the task file"
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
    Run SWE-bench agent.
    """
    with open(task_file, "r", encoding="utf-8") as handle:
        task = SWEBenchTaskInput.model_validate(json.load(handle))

    result = asyncio.run(_run(task))

    print(result.final_answer)
