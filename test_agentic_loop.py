"""Test the Agentic Loop implementation."""
import asyncio
from agenticloop.classes.AgenticLoop import AgenticLoop
from sandbox.config.SandboxConfig import SandboxConfig


async def test_basic():
    """Test basic agentic loop functionality."""
    config = SandboxConfig(
        max_execution_time_seconds=30,
        max_memory_mb=512,
    )

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
            print(f"\n✓ Execution History ({len(result.history)} entries):")
            for i, entry in enumerate(result.history, 1):
                print(f"\n  Entry {i}:")
                if "thought" in entry and entry["thought"]:
                    thought = entry["thought"][:100]
                    print(f"    Thought: {thought}...")
                if "error" in entry and entry["error"]:
                    error = entry["error"][:100]
                    print(f"    Error: {error}...")
                if "final_answer" in entry and entry["final_answer"]:
                    print(f"    Answer: {entry['final_answer']}")

        print(f"\n{'='*60}\n")

    finally:
        loop.close()


if __name__ == "__main__":
    asyncio.run(test_basic())
