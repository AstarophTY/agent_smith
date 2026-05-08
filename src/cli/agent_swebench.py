import json

import typer

from models.SWEBenchTaskInput import SWEBenchTaskInput


app = typer.Typer()


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

    print("Running SWE-bench agent with:")
    print(f"  Task file: {task_file}")
    print(f"  Output: {output}")
    print(f"  Model: {model_name}")
    print(f"  Provider URL: {provider_url}")
    print(f"  Validated instance ID: {task.instance_id}")
    # TODO: Implement agent logic
