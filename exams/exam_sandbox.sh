#!/bin/bash

# Default values
STUDENT_PATH="./student"
MOULINETTE_PATH="./moulinette"
ENV_FILE=".env"

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --student-path) STUDENT_PATH="$2"; shift ;;
        --moulinette-path) MOULINETTE_PATH="$2"; shift ;;
        --env-file) ENV_FILE="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

if [ -z "$ENV_FILE" ]; then
    echo "Error: --env-file is required"
    exit 1
fi

# Load environment variables
if [ -f "$ENV_FILE" ]; then
    export $(grep -v '^#' "$ENV_FILE" | xargs)
fi

# Add student path and its src to PYTHONPATH
export PYTHONPATH="$STUDENT_PATH/src:$PYTHONPATH"

# Path to sandbox config template
CONFIG_TEMPLATE="$STUDENT_PATH/sandbox_template.json"
if [ ! -f "$CONFIG_TEMPLATE" ]; then
    # Fallback to current dir if not in student path
    CONFIG_TEMPLATE="sandbox_template.json"
fi

# Function to run a sandbox test
# Usage: run_test <test_name> <python_code> <expected_error_or_success>
run_test() {
    local test_name=$1
    local test_code=$2
    local expected=$3
    
    echo -n "Running $test_name... "
    
    # Run the student's sandbox CLI using uv run to ensure dependencies and entry points are correct
    # We send the code and an empty line to trigger execution in interactive mode
    # We also send 'exit' to quit the interactive loop
    output=$( (echo "$test_code"; echo ""; echo "exit") | uv run --project "$STUDENT_PATH" sandbox "$CONFIG_TEMPLATE" 2>&1 )
    
    if echo "$output" | grep -qi "$expected"; then
        echo -e "\e[32mPASS\e[0m"
        return 0
    else
        echo -e "\e[31mFAIL\e[0m"
        echo "Expected to find: $expected"
        echo "Output was:"
        echo "-----------------------------------"
        echo "$output"
        echo "-----------------------------------"
        return 1
    fi
}

FAILED=0

# Security tests

# 1. import block - Should fail with SecurityException or Import not allowed
TEST_IMPORT_BLOCK="import os
print(os.listdir('.'))"
run_test "import_block" "$TEST_IMPORT_BLOCK" "SecurityException" || FAILED=$((FAILED + 1))

# 2. builtin block - Should fail with SecurityException or Call not allowed: open
TEST_BUILTIN_BLOCK="open('test.txt', 'w').write('hello')"
run_test "builtin_block" "$TEST_BUILTIN_BLOCK" "SecurityException" || FAILED=$((FAILED + 1))

# 3. network block - Should fail because socket is not in authorized_imports
TEST_NETWORK_BLOCK="import socket
socket.create_connection(('8.8.8.8', 53))"
run_test "network_block" "$TEST_NETWORK_BLOCK" "SecurityException" || FAILED=$((FAILED + 1))

# 4. path restrict - Should fail either by import block or by not having open
TEST_PATH_RESTRICT="with open('/etc/passwd', 'r') as f:
    print(f.read(10))"
run_test "path_restrict" "$TEST_PATH_RESTRICT" "SecurityException" || FAILED=$((FAILED + 1))

# 5. timeout - Should fail with "Execution timed out"
# We need a loop that doesn't rely on blocked imports
TEST_TIMEOUT="
x = 0
while True:
    x += 1"
run_test "timeout" "$TEST_TIMEOUT" "timed out" || FAILED=$((FAILED + 1))

# 6. memory limit - Should fail with MemoryError or similar
TEST_MEMORY_LIMIT="a = [0] * (10**8)"
run_test "memory_limit" "$TEST_MEMORY_LIMIT" "MemoryError\|timed out" || FAILED=$((FAILED + 1))

# 7. MCP protocol - Should succeed and show manual and final answer
TEST_MCP_PROTOCOL="print(generate_manual())
final_answer('done')"
run_test "mcp_protocol" "$TEST_MCP_PROTOCOL" "Final answer" || FAILED=$((FAILED + 1))

if [ $FAILED -eq 0 ]; then
    echo "ALL sandbox security tests passed!"
    exit 0
else
    echo "$FAILED tests failed."
    exit 1
fi
