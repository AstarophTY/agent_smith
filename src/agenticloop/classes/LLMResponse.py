from typing import Optional

from pydantic import BaseModel


class LLMResponse(BaseModel):
    thought: str
    code: Optional[str] = None
    raw_content: str
    input_tokens: int = 0
    output_tokens: int = 0
    retries: int = 0
    request_time_ms: float = 0.0
