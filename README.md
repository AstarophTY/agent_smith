*This project has been created as part of the 42 curriculum by trgascoi, sgil--de.*

# Agent Smith

## Description
Agent Smith is an autonomous reasoning and code-generation agent that solves
two types of benchmarks:
- MBPP: single-function Python problems with unit tests.
- SWE-bench: bug-fix tasks in real repositories executed inside Docker.

The agent runs a loop of LLM calls, sandboxed execution, and tool usage, then
outputs a structured solution JSON artifact for evaluation.

## Results

SWE-bench tasks solved by the agent (full tables, per-step metrics and ablation study in
[BENCHMARK.md](BENCHMARK.md)):

| Model | Provider | django-11066 | scikit-learn-13439 | sympy-18189 | Solved |
| --- | --- | :---: | :---: | :---: | :---: |
| codestral-latest | Mistral | ✅ | ✅ | ❌ | **2/3** |
| mistral-medium-latest | Mistral | ✅ | ✅ | ❌ | **2/3** |
| DeepSeek-V3 | DeepInfra | ✅ | ✅ | ❌ | **2/3** |
| mistral-small-latest | Mistral | ✅ | ❌ | ❌ | 1/3 |
| llama-3.3-70b-versatile | Groq | ✅ | ❌ | ❌ | 1/3 |

- **Selected model:** `codestral-latest`, solving 2 of 3 tasks with the fewest iterations (3 on Django, 9 on
  scikit-learn).
- **Ablation:** printing results by default and waiting when the token limit is reached turned two failures into
  passes for `mistral-small-latest`.

## System Architecture
High-level flow:

```
CLI (Typer)
	-> AgenticLoop (LLM orchestration)
		 -> Model (LLM API)
		 -> Sandbox (secure execution)
				-> SandboxSession (worker process)
				-> ToolRegistry (MCP tool proxies)
		 -> LocalToolsClient / MCP Server (tool dispatch)
	-> SolutionOutput (metrics + answer)
```

## Agent Loop Explanation
The `AgenticLoop` drives the solve cycle:
1. Build a system prompt (MBPP vs SWE-bench) and task context.
2. Call the LLM and extract a single Python code block.
3. Execute the code in the sandbox and collect stdout/stderr/error signals.
4. For MBPP, run canonical tests from the task to validate correctness.
5. Track per-step metrics and stop on `final_answer` or successful tests.

Loop state, caching, and per-step metrics are stored in the `AgenticLoopResult`.

## Sandbox Design
The sandbox isolates execution in a persistent worker process and applies
multiple safety layers:
- AST validation: only allowlisted imports and call targets are permitted, and
	special attributes (`__class__`, `__globals__`…) are rejected, including through
	`getattr`/`setattr`, to block object-graph escapes.
- Restricted builtins: a curated subset of Python builtins is exposed.
- Resource limits: CPU time and memory caps are enforced per execution.
- Tool bridging: MCP tools are exposed via proxy functions over pipes.
- `final_answer` is implemented as an exception signal to end execution cleanly.

Configuration defaults (imports, time, memory) live in
[src/models/SandboxConfig.py](src/models/SandboxConfig.py).

## Tool Implementation Details
Two tool sets are provided, injected into the sandbox through a local MCP-style
client:
- MBPP tools: [mcp_tools_mbpp.py](mcp_tools_mbpp.py)
	- `run_tests(code, test_list, test_imports)` strips any `assert` lines from
		`code`, appends the tests, and runs everything in a fresh subprocess.
		Returns `stdout`, `stderr`, `exit_code`, `success`, and a `summary`.
	- `run_code(code)` writes the snippet to a temporary file, executes it in a
		fresh subprocess, and returns `stdout`, `stderr`, `exit_code`, and `success`.
- SWE-bench tools: [mcp_tools_swebench.py](mcp_tools_swebench.py)
	- `run_command(command, workdir)` runs a shell command in the container after
		`cd` to `workdir`, returning `stdout`, `stderr`, and `exit_code`.
	- `read_file(filepath, start_line, end_line)` returns numbered lines for a
		requested range, with explicit error messages on invalid ranges.
	- `edit_file(filepath, old_str, new_str)` replaces a single exact match and
		rejects missing or multiple occurrences.
	- `list_files(directory, pattern)` lists files in the container using `find`.
	- `search_code(pattern, file_pattern)` runs `grep` with exclusions and output
		limits to avoid oversized responses.
	- `search_function_or_class_definition_in_code(name, directory)` parses
		Python files and returns matching definition lines.
	- `find_references(name, directory)` parses Python files and returns matching
		reference lines.
	- `run_tests()` executes `agent-smith-test.sh` and infers pass/fail from
		pytest, Django, or placeholder summaries (never trusts exit code alone).
	- `get_patch()` returns a unified git diff from the container.

The LocalToolsClient in [src/cli/sandbox.py](src/cli/sandbox.py) builds tool
schemas and exposes them to the sandbox. The MCP server can also expose tools
via stdio or streamable HTTP.

## Instructions

### Prerequisites
- Python 3.10+ and `uv` installed.

### Quick install (Makefile)
```bash
make install
```

### Tests and lint
```bash
uv run pytest   # sandbox security tests
make lint       # flake8 + mypy
```

### Run the CLIs

- Interactive sandbox
```bash
uv run sandbox sandbox_template.json --mcp-stdio "python mcp_tools_swebench.py"
```

- MBPP agent
```bash
uv run agent_mbpp \
	--task-file moulinette/task.json \
	--output solution.json \
	--model-name mistral-small-latest \
	--provider-url https://api.mistral.ai/v1
```

- SWE-bench agent
```bash
uv run agent_swebench \
	--task-file moulinette/task.json \
	--output solution.json \
	--model-name mistral-small-latest \
	--provider-url https://api.mistral.ai/v1
```

## Resources

All researches have been done with AI.

The different AI providers are listed in the subject.
