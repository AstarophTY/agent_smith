#!/usr/bin/env bash
set -euo pipefail

RESET=$'\033[0m'
RED=$'\033[31m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
BLUE=$'\033[34m'
MAGENTA=$'\033[35m'
CYAN=$'\033[36m'

STUDENT_PATH="$(pwd)"
MOULINETTE_PATH="$STUDENT_PATH/moulinette"
ENV_FILE="$STUDENT_PATH/.env"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --student-path)
      STUDENT_PATH="$2"
      shift 2
      ;;
    --moulinette-path)
      MOULINETTE_PATH="$2"
      shift 2
      ;;
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    *)
      printf "%sUnknown option: %s%s\n" "$RED" "$1" "$RESET"
      exit 2
      ;;
  esac
done

if [[ -f "$ENV_FILE" ]]; then
  set -a
  . "$ENV_FILE"
  set +a
fi

if [[ -z "${LLM_MODEL:-}" || -z "${LLM_BASE_URL:-}" ]]; then
  printf "%sLLM_MODEL or LLM_BASE_URL missing in env%s\n" "$RED" "$RESET"
  exit 2
fi

DATE_STR="$(date +%Y-%m-%d_%H-%M-%S)"
BASE_EVAL="$STUDENT_PATH/evaluations"
SWEBENCH_OUT="$BASE_EVAL/swebench/$DATE_STR"
mkdir -p "$SWEBENCH_OUT"

printf "%sSWE-bench: 3 random tasks%s\n" "$CYAN" "$RESET"

selection_json="$SWEBENCH_OUT/selection.json"
(cd "$MOULINETTE_PATH" && uv run moulinette_eval select swebench --count 3 --output "$selection_json")

SWEBENCH_TASKS=$(cd "$STUDENT_PATH" && uv run python - <<PY
import json
with open("$selection_json", "r", encoding="utf-8") as f:
    data = json.load(f)
print(" ".join(data.get("instance_ids", [])))
PY
)

if [[ -z "$SWEBENCH_TASKS" ]]; then
  printf "%sNo SWE-bench tasks selected%s\n" "$RED" "$RESET"
  exit 1
fi

swebench_pass=0
swebench_total=0

for instance_id in $SWEBENCH_TASKS; do
  swebench_total=$((swebench_total + 1))
  task_dir="$SWEBENCH_OUT/$instance_id"
  mkdir -p "$task_dir"
  printf "%sSWE-bench task %s%s\n" "$BLUE" "$instance_id" "$RESET"

  (cd "$MOULINETTE_PATH" && uv run moulinette_eval dump swebench --task-id "$instance_id" --output "$task_dir/task.json")
  (cd "$STUDENT_PATH" && uv run agent_swebench --task-file "$task_dir/task.json" --output "$task_dir/solution.json")

  if (cd "$MOULINETTE_PATH" && uv run moulinette_eval validate swebench "$task_dir/task.json" "$task_dir/solution.json"); then
    swebench_pass=$((swebench_pass + 1))
    printf "%sSWE-bench %s PASSED%s\n" "$GREEN" "$instance_id" "$RESET"
  else
    printf "%sSWE-bench %s FAILED%s\n" "$RED" "$instance_id" "$RESET"
  fi

  if command -v docker >/dev/null 2>&1; then
    docker ps -aq --filter status=exited --filter status=dead | xargs -r docker rm -f >/dev/null 2>&1 || true
  fi
done

printf "%sSWE-bench result: %s/%s%s\n" "$MAGENTA" "$swebench_pass" "$swebench_total" "$RESET"

if [[ "$swebench_pass" -ge 2 ]]; then
  printf "%sSWE-bench EXAM PASSED%s\n" "$GREEN" "$RESET"
  exit 0
fi

printf "%sSWE-bench EXAM FAILED%s\n" "$RED" "$RESET"
exit 1
