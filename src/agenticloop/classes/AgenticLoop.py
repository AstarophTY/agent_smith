import re
from typing import Optional, Any
from logger.classes.Logger import Logger
from agenticloop.classes.Model import Model, LLMResponse
from sandbox.core.Sandbox import Sandbox
from sandbox.config.SandboxConfig import SandboxConfig


class AgenticLoopResult:
    """Result of an agentic loop execution."""
    def __init__(self):
        self.iterations = 0
        self.final_code = None
        self.final_answer: Optional[str] = None
        self.history: list[dict[str, Any]] = []
        self.success: bool = False
        self.error_message: Optional[str] = None


class AgenticLoop:
    def __init__(
        self,
        max_iterations: int = 10,
        sandbox_config: Optional[SandboxConfig] = None,
    ):
        if not Logger._initialized:
            Logger.setup("a", "b")
        self.max_iterations = max_iterations
        self.model = Model()
        self.sandbox = Sandbox(config=sandbox_config)

    def _extract_code(self, llm_response: LLMResponse) -> Optional[str]:
        if llm_response.code:
            Logger.debug("Using code already extracted by Model")
            return llm_response.code

        Logger.debug("Model didn't find code, trying fallback extraction in AgenticLoop")
        code_match = re.search(
            r"```python\s+(.*?)\s+```",
            llm_response.raw_content,
            re.DOTALL
        )
        if code_match:
            Logger.debug("Fallback extraction found python code block")
        else:
            Logger.debug("Fallback extraction failed to find python code block")
            
        return code_match.group(1).strip() if code_match else None

    def _build_context_message(
        self,
        task: str,
        iteration: int,
        history: list[dict[str, Any]]
    ) -> str:
        context = f"Task: {task}\n\n"

        if history:
            context += "Previous attempts:\n"
            for i, entry in enumerate(history, 1):
                context += f"\nAttempt {i}:\n"
                if "code" in entry:
                    context += f"Code:\n{entry['code']}\n"
                if "error" in entry:
                    context += f"Error: {entry['error']}\n"
                if "stdout" in entry:
                    context += f"Output: {entry['stdout']}\n"

        context += f"\n--- Iteration {iteration + 1} ---\n"
        context += "Please provide the next step of code to solve this task.\n"
        context += "Include your code in a Python code block:\n"
        context += "    ```python ... ```\n"
        context += "IMPORTANT: When you have the final answer, call:\n"
        context += "    final_answer(your_answer_here)\n"
        context += "For example: final_answer(15) or final_answer('result')\n"

        return context

    async def run(
        self,
        task: str,
        initial_code: Optional[str] = None
    ) -> AgenticLoopResult:
        result = AgenticLoopResult()
        history: list[dict[str, Any]] = []
        messages: list[dict[str, str]] = []

        Logger.info(f"Starting agentic loop for task: {task}")

        if initial_code:
            Logger.info("Executing initial code...")
            sandbox_result = self.sandbox.execute(initial_code)

            history.append({
                "type": "initial_execution",
                "code": initial_code,
                "stdout": sandbox_result.stdout,
                "stderr": sandbox_result.stderr,
                "error": sandbox_result.error,
                "final_answer": sandbox_result.final_answer,
            })

            result.history = history

            if sandbox_result.final_answer:
                result.final_answer = sandbox_result.final_answer
                result.success = True
                result.iterations = 1
                result.final_code = initial_code
                return result

        for iteration in range(self.max_iterations):
            result.iterations = iteration + 1

            Logger.info(f"Iteration {iteration + 1}: Calling LLM...")
            context_message = self._build_context_message(
                task, iteration, history
            )

            try:
                llm_response = await self.model.get_next_step(
                    context_message,
                    history=messages
                )
            except Exception as e:
                Logger.error(f"LLM call failed: {e}")
                result.error_message = f"LLM call failed: {e}"
                result.success = False
                result.history = history
                return result

            messages.append({
                "role": "user",
                "content": context_message
            })
            messages.append({
                "role": "assistant",
                "content": llm_response.raw_content
            })

            code = self._extract_code(llm_response)

            if not code:
                Logger.warning("No code found in LLM response")
                history.append({
                    "type": "llm_response",
                    "thought": llm_response.thought,
                    "code": None,
                    "error": "No code found in response",
                })
                continue

            Logger.debug(f"Extracted code:\n{code}")
            result.final_code = code

            Logger.info("Executing code in sandbox...")
            try:
                sandbox_result = self.sandbox.execute(code)
            except Exception as e:
                Logger.error(f"Sandbox execution failed: {e}")
                history.append({
                    "type": "execution",
                    "code": code,
                    "error": str(e),
                })
                continue

            Logger.debug(f"Sandbox output: {sandbox_result.stdout}")
            if sandbox_result.stderr:
                Logger.debug(f"Sandbox stderr: {sandbox_result.stderr}")
            if sandbox_result.error:
                Logger.debug(f"Sandbox error: {sandbox_result.error}")

            history.append({
                "type": "execution",
                "code": code,
                "thought": llm_response.thought,
                "stdout": sandbox_result.stdout,
                "stderr": sandbox_result.stderr,
                "error": sandbox_result.error,
                "final_answer": sandbox_result.final_answer,
                "timed_out": sandbox_result.timed_out,
            })

            if sandbox_result.final_answer is not None:
                result.final_answer = sandbox_result.final_answer
                result.success = True
                result.iterations = iteration + 1
                Logger.info(
                    f"Task completed in {iteration + 1} iterations"
                )
                result.history = history
                return result

            if sandbox_result.error or sandbox_result.stderr:
                Logger.warning("Error occurred, continuing iteration")
                continue

        error_msg = (
            f"Maximum iterations ({self.max_iterations}) reached "
            "without solution"
        )
        result.error_message = error_msg
        result.history = history
        Logger.warning(result.error_message)

        return result

    def close(self) -> None:
        self.sandbox.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()
