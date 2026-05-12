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
MBPP_OUT="$BASE_EVAL/mbpp/$DATE_STR"
mkdir -p "$MBPP_OUT"

printf "%sMBPP: 5 random tasks%s\n" "$CYAN" "$RESET"

MBPP_TASKS=$(cd "$STUDENT_PATH" && uv run python - <<PY
import json, random, os
path = os.path.join("$MOULINETTE_PATH", "moulinette", "mbpp", "data", "sanitized_tasks.json")
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
pool = [t["task_id"] for t in data if t.get("split") == "test"]
random.shuffle(pool)
print(" ".join(str(x) for x in pool[:5]))
PY
)

if [[ -z "$MBPP_TASKS" ]]; then
  printf "%sNo MBPP tasks selected%s\n" "$RED" "$RESET"
  exit 1
fi

mbpp_pass=0
mbpp_total=0

for task_id in $MBPP_TASKS; do
  mbpp_total=$((mbpp_total + 1))
  task_dir="$MBPP_OUT/$task_id"
  mkdir -p "$task_dir"
  printf "%sMBPP task %s%s\n" "$BLUE" "$task_id" "$RESET"

  (cd "$MOULINETTE_PATH" && uv run moulinette_eval dump mbpp --task-id "$task_id" --output "$task_dir/task.json")
  (cd "$STUDENT_PATH" && uv run agent_mbpp --task-file "$task_dir/task.json" --output "$task_dir/solution.json")

  if (cd "$MOULINETTE_PATH" && uv run moulinette_eval validate mbpp "$task_dir/task.json" "$task_dir/solution.json"); then
    mbpp_pass=$((mbpp_pass + 1))
    printf "%sMBPP %s PASSED%s\n" "$GREEN" "$task_id" "$RESET"
  else
    printf "%sMBPP %s FAILED%s\n" "$RED" "$task_id" "$RESET"
  fi
done

printf "%sMBPP result: %s/%s%s\n" "$MAGENTA" "$mbpp_pass" "$mbpp_total" "$RESET"

if [[ "$mbpp_pass" -ge 4 ]]; then
  printf "%sMBPP EXAM PASSED%s\n" "$GREEN" "$RESET"
  exit 0
fi

printf "%sMBPP EXAM FAILED%s\n" "$RED" "$RESET"
exit 1
