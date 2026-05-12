import re
import shutil
import time
from datetime import datetime
from typing import Any, List, Optional
from types import ModuleType

from agenticloop.classes.LLMResponse import LLMResponse
from logger.classes.Logger import Logger
from agenticloop.classes.Model import Model
from sandbox.core.Sandbox import Sandbox
from models import SandboxConfig, SWEBenchTaskInput, MBPPTaskInput
from models.StepMetrics import StepMetrics
from mcp_sys.Containerizer import Containerizer
from cli.sandbox import LocalToolsClient


MBPP_MAX_INPUT_TOKENS = 6_000
MBPP_MAX_OUTPUT_TOKENS = 1_500
SWEBENCH_MAX_INPUT_TOKENS = 300_000
SWEBENCH_MAX_OUTPUT_TOKENS = 10_000

MBPP_SYSTEM_PROMPT = """\
You are Agent Smith, an autonomous Python coding agent.

## Task
Implement a Python function that passes all provided tests.

## Available Tools
- run_tests(code, test_list, test_imports): Runs your implementation
    against tests.
    - code: your complete function as a string
        (can include imports at the top)
    - test_list: list of assert strings
        (e.g. ["assert f(1) == 2", "assert f(0) == 0"])
    - test_imports: list of extra import lines needed by the tests
        (e.g. ["import math"])
    Returns: {"stdout": str, "stderr": str, "exit_code": int,
    "success": bool}
  (The result is also printed automatically).
    success=True means ALL assertions passed. stderr shows the traceback
    on failure.
- final_answer(code): Submit solution and stop. Pass ONLY the function string.

## Workflow (follow exactly)
1. Read the function signature and understand what each test expects
2. Implement the function
3. Call run_tests() with the exact test strings from the task
4. Check result["success"]:
   - True  → call final_answer(code) with the same code variable
   - False → read result["stderr"], fix the bug, retry from step 2

## Response Format
Always respond with:
Thought: <brief reasoning about the approach>
```python
<EXACTLY ONE code block containing your next action>
```

CRITICAL: Your response MUST contain exactly one Python code block.
Do NOT include any conversational text or "Thought:" inside the code block.

NOTE: All tools automatically print their results. You don't need to use
print() on tool calls.

## Pattern to follow every iteration
```python
code = \"\"\"def function_name(args):
    # implementation here
    return result\"\"\"

result = run_tests(
    code=code,
    test_list=[
        "assert function_name(arg1) == expected1",
        "assert function_name(arg2) == expected2",
    ],
    test_imports=[],  # add imports here if the tests need them
)
if result["success"]:
    final_answer(code)
else:
    print("Tests failed:", result["stderr"])
```

## Full Example
Task: Write a function add(a, b) that returns the sum of two numbers.
Function prototype: def add(a, b):
Tests to pass:
  assert add(1, 2) == 3
  assert add(-1, 1) == 0

Thought: Simple addition. Return a + b.
```python
code = \"\"\"def add(a, b):
    return a + b\"\"\"

result = run_tests(
    code=code,
    test_list=["assert add(1, 2) == 3", "assert add(-1, 1) == 0"],
    test_imports=[],
)
if result["success"]:
    final_answer(code)
else:
    print("Tests failed:", result["stderr"])
```

## Rules
- ALWAYS respond with a Python code block (```python ... ```)
    containing your next action
- Use triple-quoted strings for multi-line functions in the code variable
- ALWAYS call run_tests before final_answer — never submit without
    verifying
- If the function needs imports (math, re, etc.), include them INSIDE the
    code string
- Copy the exact test strings from the task into test_list
- Do NOT call final_answer until run_tests shows success=True
- If stuck after 3 iterations, reconsider the approach entirely
"""

SWEBENCH_SYSTEM_PROMPT_TEMPLATE = """\
You are Agent Smith, an autonomous software engineering agent fixing bugs
in real Python repositories.

## Available Tools
{tool_docs}

## Debugging Methodology
1. READ the problem statement carefully — understand what is broken
2. SEARCH for relevant code: search_code(),
   search_function_or_class_definition_in_code()
3. READ the relevant files: read_file() to understand context around the bug
4. UNDERSTAND the root cause before touching any file
5. EDIT minimally: edit_file() — change only what is necessary
6. TEST: run_tests() — check if tests pass
    (exit_code=0 means pass)
7. ITERATE: if tests still fail, re-examine the edit and fix
8. SUBMIT: patch = get_patch() then final_answer(patch)

## Response Format
Thought: <your reasoning about what to do next>
```python
<EXACTLY ONE code block containing your next action>
```

CRITICAL: Your response MUST contain exactly one Python code block.
Do NOT include any conversational text or "Thought:" inside the code block.

NOTE: All tools automatically print their results. You don't need to use
print() on tool calls.

## Interpreting run_tests()
run_tests() returns: {{"stdout": str, "stderr": str, "exit_code": int,
"passed": bool, "summary": str}}
- passed == True: all tests PASS — ready to submit
- passed == False: tests FAIL — read stdout/stderr to find which test failed
- NEVER rely on exit_code alone; the eval script may print "Test failed"
    yet exit 0. Always check the "passed" boolean and the "summary" field.

## Submitting the solution
```python
patch = get_patch()
final_answer(patch)
```

## Critical Rules
- ALWAYS respond with a Python code block (```python ... ```)
    containing your next action
- NEVER submit without running tests first
    (run_tests, check exit_code == 0)
- Make targeted, minimal edits — do not refactor unrelated code
- Do NOT access external URLs or look up PR/issue solutions
- Always verify with read_file after edit_file to confirm the change is
    correct
- The repository is at /testbed — all file paths start with /testbed/
"""


class AgenticLoopResult:
    """Result of an agentic loop execution."""

    def __init__(self) -> None:
        self.iterations: int = 0
        self.final_code: Optional[str] = None
        self.final_answer: Optional[str] = None
        self.history: list[dict[str, Any]] = []
        self.success: bool = False
        self.error_message: Optional[str] = None
        self.steps: List[StepMetrics] = []
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_requests: int = 0
        self.total_time_seconds: float = 0.0
        self.system_prompt: str = ""


class AgenticLoop:
    def __init__(
        self,
        tool_module: Optional[ModuleType] = None,
        docker_image: str = "",
        max_iterations: int = 10,
        sandbox_config: Optional[SandboxConfig] = None,
        model_name: Optional[str] = None,
        provider_url: Optional[str] = None,
    ):
        if not Logger._initialized:
            Logger.setup("a", "b")

        self.max_iterations = max_iterations
        self.model = Model(model_name=model_name, base_url=provider_url)
        self.mcp_client: Optional[LocalToolsClient] = None
        self.containerizer: Optional[Containerizer] = None

        if docker_image:
            if tool_module is None:
                raise ValueError(
                    "tool_module is required when docker_image is set"
                )
            self.containerizer = Containerizer()
            self.containerizer.up(docker_image)
            self.mcp_client = LocalToolsClient(
                tool_module, containerizer=self.containerizer
            )
            self.sandbox = Sandbox(
                config=sandbox_config, mcp_client=self.mcp_client
            )
        elif tool_module is not None:
            # MBPP and other non-docker tasks still need MCP tools
            # (e.g. run_tests).
            self.mcp_client = LocalToolsClient(tool_module)
            self.sandbox = Sandbox(
                config=sandbox_config, mcp_client=self.mcp_client
            )
        else:
            self.sandbox = Sandbox(config=sandbox_config)

        Logger.debug("AgenticLoop initialized")

    def _build_system_prompt(
        self, task: MBPPTaskInput | SWEBenchTaskInput
    ) -> str:
        if isinstance(task, MBPPTaskInput):
            return MBPP_SYSTEM_PROMPT
        tool_docs = self._build_tool_docs()
        return SWEBENCH_SYSTEM_PROMPT_TEMPLATE.format(tool_docs=tool_docs)

    def _build_tool_docs(self) -> str:
        if not self.mcp_client:
            return "No tools available."
        schemas = self.mcp_client.list_tools()
        lines: list[str] = []
        for schema in schemas:
            name = schema.get("name", "")
            description = schema.get("description", "")
            props = schema.get("inputSchema", {}).get("properties", {})
            params = ", ".join(
                f"{k}: {v.get('type', 'str')}"
                for k, v in props.items()
            )
            line_text = (
                f"- {name}({params}): "
                f"{description}"
            )
            lines.append(line_text)
        lines.append(
            "- final_answer(answer): Submit the final solution (patch string) "
            "and stop"
        )
        return "\n".join(lines)

    def _extract_code(self, llm_response: LLMResponse) -> Optional[str]:
        code = None
        if llm_response.code:
            code = llm_response.code
        else:
            code_match = re.search(
                r"```python\s+(.*?)\s*```",
                llm_response.raw_content,
                re.DOTALL,
            )
            if code_match:
                code = code_match.group(1).strip()
            else:
                code = self._xml_calls_to_python(llm_response.raw_content)

        if code:
            # Clean up the code block if the LLM included its thought
            # process inside it.
            lines = code.splitlines()
            cleaned_lines: list[str] = []
            for line in lines:
                stripped = line.strip()
                # Skip empty lines at the beginning
                if not cleaned_lines and not stripped:
                    continue
                # Skip conversational markers or thoughts leaking into code
                # block.
                if stripped.startswith("Thought:"):
                    continue
                if stripped.lower().startswith(
                    (
                        "let me",
                        "i will",
                        "i'll",
                        "i'm going to",
                        "the fix is",
                    )
                ):
                    continue

                cleaned_lines.append(line)

            # Remove trailing empty lines
            while cleaned_lines and not cleaned_lines[-1].strip():
                cleaned_lines.pop()

            code = "\n".join(cleaned_lines).strip()
            return code if code else None

        return None

    def _xml_calls_to_python(self, text: str) -> Optional[str]:
        """Convert Mistral-style XML function calls into equivalent Python.

        Pattern: <function=NAME> <parameter=KEY>VALUE</parameter>...
        </function>
        Mistral and some other models emit this format natively when they're
        trained on XML tool-calling — even after a prompt asks for Python.
        Rather than dropping the response, we translate it.
        """
        func_pattern = re.compile(
            r"<function=([\w_]+)>\s*(.*?)\s*(?:</function>|$)",
            re.DOTALL,
        )
        param_pattern = re.compile(
            r"<parameter=([\w_]+)>\s*(.*?)\s*(?:</parameter>|$)",
            re.DOTALL,
        )
        lines: list[str] = []
        for func_name, body in func_pattern.findall(text):
            params: list[str] = []
            for key, value in param_pattern.findall(body):
                value = value.strip()
                if not value:
                    continue
                if re.fullmatch(r"-?\d+", value):
                    params.append(f"{key}={value}")
                elif re.fullmatch(r"-?\d+\.\d+", value):
                    params.append(f"{key}={value}")
                elif value in ("True", "False", "None"):
                    params.append(f"{key}={value}")
                else:
                    params.append(f"{key}={value!r}")
            args = ", ".join(params)
            if func_name == "final_answer":
                lines.append(f"{func_name}({args})")
            else:
                lines.append(f"result = {func_name}({args})")
        if not lines:
            return None
        return "\n".join(lines)

    def _build_mbpp_test_code(
        self, task: MBPPTaskInput, candidate_code: str
    ) -> str:
        """Build canonical test code from the candidate function."""
        candidate_core = self._strip_assert_lines(candidate_code)
        lines: list[str] = [
            "def final_answer(*args, **kwargs):",
            "    return None",
            "",
            candidate_core,
            "",
        ]
        if task.test_imports:
            lines.extend(task.test_imports)
            lines.append("")
        lines.extend(task.test_list)
        return "\n".join(lines)

    def _strip_assert_lines(self, code: str) -> str:
        cleaned = [
            line
            for line in code.splitlines()
            if not line.strip().startswith("assert ")
        ]
        return "\n".join(cleaned).strip()

    def _boxed_text(self, text: str, max_lines: int = 10) -> str:
        lines = text.splitlines() or [""]
        terminal_width = shutil.get_terminal_size((120, 20)).columns
        max_width = max(20, terminal_width - 6)

        if len(lines) > max_lines:
            visible = lines[: max_lines - 1]
            hidden_count = len(lines) - (max_lines - 1)
            visible.append(f"... (+{hidden_count} lines)")
        else:
            visible = lines

        trimmed: list[str] = []
        for line in visible:
            if len(line) > max_width:
                trimmed.append(line[: max_width - 3] + "...")
            else:
                trimmed.append(line)

        inner_width = max_width
        top = "┌" + ("─" * (inner_width + 2)) + "┐"
        bottom = "└" + ("─" * (inner_width + 2)) + "┘"
        body = [
            f"│ {line.ljust(inner_width)} │"
            for line in trimmed
        ]
        return "\n".join([top, *body, bottom])

    def _build_observation(
        self,
        sandbox_stdout: str,
        sandbox_stderr: str,
        sandbox_error: Optional[str],
        timed_out: bool,
        tests_error: Optional[str] = None,
        tests_stderr: str = "",
        tests_timed_out: bool = False,
        tests_passed: Optional[bool] = None,
        no_code_found: bool = False,
    ) -> str:
        if no_code_found:
            return (
                "[SYSTEM] No valid Python code block found in your response.\n"
                "Please include your code inside ```python ... ``` markers.\n"
                "Follow the response format exactly as shown in the "
                "instructions.\n"
                "If you've already tried something that didn't work, try a "
                "different approach."
            )

        parts: list[str] = []

        if timed_out:
            parts.append(
                "[SYSTEM] Sandbox execution timed out. Output so far "
                "(partial):"
            )

        if sandbox_stdout:
            parts.append(f"stdout:\n{sandbox_stdout}")
        if sandbox_stderr:
            parts.append(f"stderr:\n{sandbox_stderr}")
        if sandbox_error:
            parts.append(f"error:\n{sandbox_error}")

        if tests_timed_out:
            parts.append("[SYSTEM] Canonical test execution timed out.")
        elif tests_passed is True:
            parts.append("[SYSTEM] Canonical tests: ALL PASSED ✓")
        elif tests_passed is False:
            parts.append("[SYSTEM] Canonical tests: FAILED ✗")
            if tests_error:
                parts.append(f"Test error:\n{tests_error}")
            if tests_stderr:
                parts.append(f"Test stderr:\n{tests_stderr}")

        if not parts:
            parts.append(
                "(no output — code executed successfully with no output)"
            )

        return "\n".join(parts)

    def _make_step(
        self,
        iteration: int,
        llm_response: LLMResponse,
        sandbox_input: str,
        sandbox_output: str,
    ) -> StepMetrics:
        return StepMetrics(
            step=iteration + 1,
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
            request_time_ms=llm_response.request_time_ms,
            api_url=self.model.base_url,
            model_name=self.model.model_name,
            llm_output=llm_response.raw_content,
            sandbox_input=sandbox_input,
            sandbox_output=sandbox_output,
            retries=llm_response.retries,
            timestamp=datetime.now().isoformat(),
        )

    async def run(
        self,
        task: MBPPTaskInput | SWEBenchTaskInput,
        initial_code: Optional[str] = None,
    ) -> AgenticLoopResult:
        _ = initial_code  # reserved for future use
        result = AgenticLoopResult()
        history: list[dict[str, Any]] = []
        # Cache: normalized_code -> (observation, run_count). Reused when
        # the agent issues an identical call, but invalidated whenever a
        # state-changing call (edit_file/run_tests/run_command) is made.
        exec_cache: dict[str, tuple[str, int]] = {}
        start_time = time.time()

        system_prompt = self._build_system_prompt(task)
        result.system_prompt = system_prompt

        is_mbpp = isinstance(task, MBPPTaskInput)
        max_input = (
            MBPP_MAX_INPUT_TOKENS if is_mbpp
            else SWEBENCH_MAX_INPUT_TOKENS
        )
        max_output = (
            MBPP_MAX_OUTPUT_TOKENS if is_mbpp
            else SWEBENCH_MAX_OUTPUT_TOKENS
        )

        if is_mbpp:
            assert isinstance(task, MBPPTaskInput)
            task_str = (
                f"Task: {task.task_definition}\n"
                f"Function prototype: {task.function_definition}\n"
                "Tests to pass:\n"
                + "\n".join(f"  {t}" for t in task.test_list)
            )
            if task.test_imports:
                task_str += "\nTest imports:\n" + "\n".join(
                    f"  {i}" for i in task.test_imports
                )
        else:
            assert isinstance(task, SWEBenchTaskInput)
            import shlex
            self.containerizer.cmd(  # type: ignore[union-attr]
                f"printf '%s' {shlex.quote(task.eval_script)}"
                " > /testbed/agent-smith-test.sh"
            )
            task_str = task.problem_statement
            if task.hints_text:
                task_str += f"\n\nHints:\n{task.hints_text}"
            if task.repo:
                task_str += (
                    f"\n\nRepository: {task.repo} "
                    "(mounted at /testbed)"
                )

        try:
            for iteration in range(self.max_iterations):
                result.iterations = iteration + 1
                Logger.info(
                    f"=== Iteration {iteration + 1}/{self.max_iterations} ==="
                )

                if result.total_input_tokens >= max_input:
                    Logger.warning("Input token limit reached, stopping")
                    result.error_message = "Input token limit reached"
                    break
                if result.total_output_tokens >= max_output:
                    Logger.warning("Output token limit reached, stopping")
                    result.error_message = "Output token limit reached"
                    break

                context_parts = [task_str]
                if history:
                    context_parts.append("\nPrevious steps:")
                    for i, entry in enumerate(history[-5:], 1):
                        thought = entry.get("thought", "")
                        if thought:
                            context_parts.append(
                                f"\nStep {i} thought:\n{thought}"
                            )
                        context_parts.append(
                            f"Step {i} code:\n{entry.get('code', '')}"
                        )
                        obs = entry.get("observation", "")
                        if obs:
                            context_parts.append(f"Observation:\n{obs}")

                if history and not history[-1].get("code"):
                    context_parts.append(
                        "\nIMPORTANT: Your previous response did not contain "
                        "a valid Python code block. You MUST provide your "
                        "next action as a Python code block using the tools "
                        "available. Do NOT include your 'Thought:' or any "
                        "conversational text inside the code block. Your "
                        "response must contain EXACTLY ONE code block "
                        "(```python ... ```). If you are stuck or your "
                        "previous action failed, try a DIFFERENT approach."
                    )

                context_message = "\n".join(context_parts)

                Logger.info("Calling LLM...")
                try:
                    llm_response = await self.model.get_next_step(
                        context_message,
                        system_prompt=system_prompt,
                    )
                except Exception as e:
                    Logger.error(f"LLM call failed: {e}")
                    result.error_message = f"LLM call failed: {e}"
                    break

                result.total_input_tokens += llm_response.input_tokens
                result.total_output_tokens += llm_response.output_tokens
                result.total_requests += 1

                code = self._extract_code(llm_response)

                if not code:
                    Logger.warning("No code block in LLM response")
                    obs = self._build_observation(
                        sandbox_stdout="",
                        sandbox_stderr="",
                        sandbox_error=None,
                        timed_out=False,
                        no_code_found=True,
                    )
                    result.steps.append(
                        self._make_step(iteration, llm_response, "", obs)
                    )
                    history.append({
                        "thought": llm_response.thought,
                        "code": None,
                        "observation": obs,
                    })
                    continue

                Logger.info(f"Code:\n{self._boxed_text(code)}")
                result.final_code = code

                normalized = " ".join(code.split())
                mutates_state = any(
                    tok in normalized
                    for tok in (
                        "edit_file(",
                        "run_tests(",
                        "run_command(",
                        "final_answer(",
                    )
                )
                if mutates_state:
                    exec_cache.clear()

                cached = exec_cache.get(normalized)
                if cached is not None:
                    prev_obs, prev_count = cached
                    new_count = prev_count + 1
                    exec_cache[normalized] = (prev_obs, new_count)
                    Logger.warning(
                        f"Cache hit: identical call run {new_count} times, "
                        "skipping sandbox and reusing previous result"
                    )
                    if new_count >= 3:
                        obs = (
                            f"[SYSTEM] You ran this exact code {new_count} "
                            "times. The result is deterministic — re-calling "
                            "is wasted compute. You MUST change your strategy "
                            "or parameters."
                        )
                        Logger.warning(
                            "Forcing strategy change after "
                            f"{new_count} repetitions"
                        )
                    else:
                        obs = (
                            "[SYSTEM] Duplicate call — you already ran this "
                            f"exact code {prev_count} time(s). Returning the "
                            "previous observation as-is (no re-execution). "
                            "IMPORTANT: Repeating the same call will NOT "
                            "change the result. Use this result and try a "
                            "DIFFERENT action or change your approach.\n\n"
                            f"Previous observation:\n{prev_obs}"
                        )
                    result.steps.append(
                        self._make_step(iteration, llm_response, code, obs)
                    )
                    history.append({
                        "thought": llm_response.thought,
                        "code": code,
                        "observation": obs,
                    })
                    continue

                try:
                    sandbox_result = self.sandbox.execute(code)
                except (KeyboardInterrupt, SystemExit):
                    raise
                except Exception as e:
                    Logger.error(f"Sandbox execution error: {e}")
                    obs = f"[SYSTEM] Sandbox error: {e}"
                    result.steps.append(
                        self._make_step(iteration, llm_response, code, obs)
                    )
                    history.append({
                        "thought": llm_response.thought,
                        "code": code,
                        "observation": obs,
                    })
                    continue

                # Run canonical MBPP tests to verify correctness independently
                tests_error: Optional[str] = None
                tests_stderr: str = ""
                tests_timed_out: bool = False
                canonical_tests_ran: bool = False
                tests_passed_flag: Optional[bool] = None

                if not sandbox_result.error:
                    normalized = " ".join(code.split())
                    exec_cache[normalized] = (
                        sandbox_result.stdout + sandbox_result.stderr,
                        1,
                    )

                if is_mbpp and not sandbox_result.error:
                    assert isinstance(task, MBPPTaskInput)
                    # Prefer the final_answer string as code to test (cleaner),
                    # fall back to stripping asserts from the sandbox code
                    # block.
                    code_to_test = (
                        sandbox_result.final_answer
                        if sandbox_result.final_answer is not None
                        else self._strip_assert_lines(code)
                    )
                    test_code = self._build_mbpp_test_code(task, code_to_test)
                    Logger.info("Running canonical MBPP tests...")
                    tests_result = self.sandbox.execute(test_code)
                    tests_stderr = tests_result.stderr
                    tests_error = tests_result.error
                    tests_timed_out = tests_result.timed_out
                    canonical_tests_ran = True
                    # Tests pass when there is no exception and no timeout.
                    # Stderr may contain harmless warnings — do NOT fail on it.
                    tests_passed_val = (
                        not tests_error and not tests_timed_out
                    )
                    tests_passed_flag = tests_passed_val
                    if tests_error:
                        Logger.warning(
                            f"Canonical tests failed: {tests_error}"
                        )
                    else:
                        Logger.info("Canonical tests passed")

                obs = self._build_observation(
                    sandbox_stdout=sandbox_result.stdout,
                    sandbox_stderr=sandbox_result.stderr,
                    sandbox_error=sandbox_result.error,
                    timed_out=sandbox_result.timed_out,
                    tests_error=tests_error,
                    tests_stderr=tests_stderr,
                    tests_timed_out=tests_timed_out,
                    tests_passed=(
                        tests_passed_flag if canonical_tests_ran else None
                    ),
                )

                result.steps.append(
                    self._make_step(iteration, llm_response, code, obs)
                )
                history.append({
                    "thought": llm_response.thought,
                    "code": code,
                    "observation": obs,
                })
                if not mutates_state:
                    exec_cache[normalized] = (obs, 1)

                canonical_ok = (
                    canonical_tests_ran
                    and tests_passed_flag is True
                )

                if sandbox_result.final_answer is not None:
                    if not is_mbpp or canonical_ok:
                        result.final_answer = sandbox_result.final_answer
                        result.success = True
                        Logger.info(
                            f"Task solved in {iteration + 1} iterations"
                        )
                        break
                    else:
                        Logger.warning(
                            "final_answer called but canonical tests failed; "
                            "continuing"
                        )
                        continue

                # Auto-succeed when canonical tests pass (no explicit
                # final_answer needed)
                if is_mbpp and canonical_ok:
                    Logger.info(
                        "Canonical tests passed; extracting final answer "
                        "from code"
                    )
                    code_to_test = self._strip_assert_lines(code)
                    result.final_answer = code_to_test
                    result.success = True
                    break
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            Logger.error(f"Unexpected error in AgenticLoop.run: {e}")
            result.error_message = f"Unexpected error: {e}"

        if not result.success and not result.error_message:
            result.error_message = (
                f"Maximum iterations ({self.max_iterations}) reached"
            )
            Logger.warning(result.error_message)

        result.total_time_seconds = time.time() - start_time
        return result

    def close(self) -> None:
        if self.containerizer:
            try:
                self.containerizer.down()
            except Exception:
                pass
        self.sandbox.close()

    async def __aenter__(self) -> "AgenticLoop":
        return self

    async def __aexit__(self, *_: Any) -> None:
        self.close()
