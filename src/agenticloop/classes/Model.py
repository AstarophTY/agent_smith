import os
from openai import AsyncOpenAI
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv


class LLMResponse(BaseModel):
    thought: str
    code: Optional[str] = None
    raw_content: str


class Model:
    def __init__(self):
        load_dotenv()
        api_key = os.getenv("LLM_API_KEY", "your-api-key")
        base_url = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = os.getenv("LLM_MODEL", "google/gemini-2.0-flash-001")

    async def get_next_step(
        self,
        prompt: str,
        history: List[dict] = []
    ) -> LLMResponse:
        system_instruction = (
            "You are an autonomous coding agent named Agent Smith. "
            "Your goal is to solve complex tasks by writing and "
            "executing Python code. "
            "Always provide your reasoning first (Thought), "
            "followed by the code block formatted in Markdown "
            "(```python ... ```).\n"
            "CRITICAL: When you have solved the task and have the "
            "final answer, you MUST call:\n"
            "    final_answer(your_answer)\n"
            "For example: final_answer(42) or final_answer('done')"
        )

        messages = [{"role": "system", "content": system_instruction}]
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1
            )

            full_text = response.choices[0].message.content
            from logger.classes.Logger import Logger
            Logger.debug(f"LLM RAW RESPONSE: {full_text}")
            return self._parse_output(full_text)

        except Exception as e:
            # Let the exception propagate to AgenticLoop
            raise e

    def _parse_output(self, text: str) -> LLMResponse:
        import re
        from logger.classes.Logger import Logger

        code_match = re.search(r"```python\s+(.*?)\s+```", text, re.DOTALL)
        if code_match:
            Logger.debug("Found python code block")
        else:
            Logger.debug("No python code block found with current regex")

        code = code_match.group(1).strip() if code_match else None

        thought = re.sub(r"```python.*?```", "", text, flags=re.DOTALL).strip()

        return LLMResponse(thought=thought, code=code, raw_content=text)


if __name__ == "__main__":
    import asyncio

    async def test():
        service = Model()
        res = await service.get_next_step(
            "Write a function to extract elements that occur singly in the given tuple list. Def: def extract_singly(test_list):"
        )
        print(f"THINK : {res.thought}")
        print(f"CODE : {res.code}")

    asyncio.run(test())
