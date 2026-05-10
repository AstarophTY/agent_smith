from pydantic import BaseModel, Field


class SWEBenchTaskInput(BaseModel):
    """Input for a SWE-bench task, provided by the moulinette."""
    instance_id: str = Field(..., description="SWE-bench instance identifier")
    problem_statement: str = Field(
        ..., description="The GitHub issue description"
    )
    docker_image: str = Field(
        ..., description="Full Docker image name to pull"
    )
    eval_script: str = Field(
        ..., description="Bash script to run inside the container"
    )
    hints_text: str = Field(
        default="", description="Optional hints about the issue"
    )
    repo: str = Field(default="", description="Repository name")
