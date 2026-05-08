import json

import typer

from models.MBPPTaskInput import MBPPTaskInput


app = typer.Typer()


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

    print("Running MBPP agent with:")
    print(f"  Task file: {task_file}")
    print(f"  Output: {output}")
    print(f"  Model: {model_name}")
    print(f"  Provider URL: {provider_url}")
    print(f"  Validated task ID: {task.task_id}")
    # TODO: Implement agent logic
