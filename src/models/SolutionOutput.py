from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from .StepMetrics import StepMetrics


class SolutionOutput(BaseModel):
    """Output from student solution required for evaluation."""
    task_id: str
    benchmark: str
    success: bool
    solution: str = Field(
        ..., description="Python code for MBPP, or git patch for SWE-bench"
    )
    iterations: int
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_time_seconds: float
    steps: List[StepMetrics] = Field(default_factory=list)
    system_prompt: str = Field(default="")
    error: Optional[str] = Field(default=None)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
