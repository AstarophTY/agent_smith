"""Test the Agentic Loop with mock LLM responses."""
import asyncio
from unittest.mock import AsyncMock, patch
from agenticloop.classes.AgenticLoop import AgenticLoop
from agenticloop.classes.Model import LLMResponse
from sandbox.config.SandboxConfig import SandboxConfig


async def test_with_mock():
    config = SandboxConfig(
        max_execution_time_seconds=30,
        max_memory_mb=512,
    )

    mock_llm_response = LLMResponse(
        thought="I need to calculate 1+2+3+4+5 which equals 15.",
        code="result = 1 + 2 + 3 + 4 + 5\nfinal_answer(result)",
        raw_content=(
            "I need to calculate 1+2+3+4+5 which equals 15.\n\n"
            "```python\n"
            "result = 1 + 2 + 3 + 4 + 5\n"
            "final_answer(result)\n"
            "```"
        ),
    )

    with patch(
        "agenticloop.classes.AgenticLoop.Model.get_next_step",
        new_callable=AsyncMock,
        return_value=mock_llm_response
    ):
        loop = AgenticLoop(max_iterations=3, sandbox_config=config)

        try:
            task = "Calculate the sum of the first 5 positive integers"
            print(f"\n{'='*60}")
            print(f"Task: {task}")
            print(f"{'='*60}")

            result = await loop.run(task)

            print(f"\n✓ Success: {result.success}")
            print(f"✓ Iterations: {result.iterations}")

            if result.final_answer:
                print(f"✓ Final Answer: {result.final_answer}")

            if result.final_code:
                print(f"✓ Final Code:\n{result.final_code}")

            if result.error_message:
                print(f"✗ Error: {result.error_message}")

            if result.history:
                hist_count = len(result.history)
                print(f"\n✓ Execution History ({hist_count} entries):")
                for i, entry in enumerate(result.history, 1):
                    print(f"\n  Entry {i}:")
                    if "thought" in entry and entry["thought"]:
                        thought = entry["thought"][:100]
                        print(f"    Thought: {thought}")
                    if "stdout" in entry and entry["stdout"]:
                        print(f"    Output: {entry['stdout']}")
                    if "error" in entry and entry["error"]:
                        error = entry["error"][:80]
                        print(f"    Error: {error}...")
                    if "final_answer" in entry and entry["final_answer"]:
                        print(f"    Final Answer: {entry['final_answer']}")

            print(f"\n{'='*60}\n")

        finally:
            loop.close()


if __name__ == "__main__":
    asyncio.run(test_with_mock())
