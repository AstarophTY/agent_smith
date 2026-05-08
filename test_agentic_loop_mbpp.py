"""Test the Agentic Loop with MBPP tasks."""
import asyncio
import json
from unittest.mock import AsyncMock, patch
from agenticloop.classes.AgenticLoop import AgenticLoop
from agenticloop.classes.Model import LLMResponse
from sandbox.config.SandboxConfig import SandboxConfig


def load_mbpp_tasks():
    with open(
        "moulinette/moulinette/mbpp/data/sanitized_tasks.json", "r"
    ) as f:
        tasks = json.load(f)
    return tasks[:5]


async def test_mbpp_task(task_data, mock_response=None):
    config = SandboxConfig(
        max_execution_time_seconds=30,
        max_memory_mb=512,
    )

    if mock_response is None:
        solution_code = task_data["code"]
        mock_response = LLMResponse(
            thought=f"Implementing: {task_data['task_definition']}",
            code=solution_code,
            raw_content=f"```python\n{solution_code}\n```",
        )

    with patch(
        "agenticloop.classes.AgenticLoop.Model.get_next_step",
        new_callable=AsyncMock,
        return_value=mock_response
    ):
        loop = AgenticLoop(max_iterations=2, sandbox_config=config)

        try:
            task_desc = task_data["task_definition"]
            print(f"\n{'='*70}")
            print(f"MBPP Task #{task_data['task_id']}: {task_desc}")
            print(f"{'='*70}")

            result = await loop.run(task_desc)

            print(f"✓ Success: {result.success}")
            print(f"✓ Iterations: {result.iterations}")

            if result.final_code:
                print("\n✓ Generated Code:")
                for line in result.final_code.split("\n")[:10]:
                    print(f"  {line}")
                if len(result.final_code.split("\n")) > 10:
                    print("  ... ({len(result.final_code.split(chr(10))) - 10} more lines)")

            if result.final_answer:
                print(f"✓ Final Answer: {result.final_answer}")

            if result.error_message:
                print(f"✗ Error: {result.error_message}")

            print("\n✓ Test Cases from MBPP:")
            for i, test_case in enumerate(task_data["test_list"][:3], 1):
                print(f"  {i}. {test_case}")

            return result.success

        finally:
            loop.close()


async def test_all_mbpp_tasks():
    tasks = load_mbpp_tasks()
    results = []

    print("\n" + "="*70)
    print("AGENTIC LOOP - MBPP BENCHMARK TEST")
    print("="*70)

    for task_data in tasks:
        try:
            success = await test_mbpp_task(task_data)
            results.append({
                "task_id": task_data["task_id"],
                "task": task_data["task_definition"],
                "success": success,
            })
        except Exception as e:
            print(f"✗ Task execution failed: {e}")
            results.append({
                "task_id": task_data["task_id"],
                "task": task_data["task_definition"],
                "success": False,
            })

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    successful = sum(1 for r in results if r["success"])
    total = len(results)

    for r in results:
        status = "✓" if r["success"] else "✗"
        print(f"{status} Task #{r['task_id']}: {r['task'][:50]}...")

    print(f"\n{'='*70}")
    print(f"Results: {successful}/{total} tasks completed successfully")
    print(f"Success Rate: {100 * successful / total:.1f}%")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(test_all_mbpp_tasks())
