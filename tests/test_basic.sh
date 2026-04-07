#!/bin/bash

# AI-IQ - Basic Test Suite
# Tests core functionality in an isolated environment

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Create temporary test directory
TEST_DIR=$(mktemp -d)
export MEMORY_DIR="$TEST_DIR"

echo -e "${GREEN}AI-IQ - Basic Test Suite${NC}"
echo "===================================="
echo "Test directory: $TEST_DIR"
echo ""

# Helper function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"

    TESTS_RUN=$((TESTS_RUN + 1))
    echo -n "Test $TESTS_RUN: $test_name... "

    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN}PASS${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Helper function to run a test with expected output
run_test_output() {
    local test_name="$1"
    local test_command="$2"
    local expected_pattern="$3"

    TESTS_RUN=$((TESTS_RUN + 1))
    echo -n "Test $TESTS_RUN: $test_name... "

    OUTPUT=$(eval "$test_command" 2>&1)
    if echo "$OUTPUT" | grep -q "$expected_pattern"; then
        echo -e "${GREEN}PASS${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        echo "  Expected pattern: $expected_pattern"
        echo "  Got: $OUTPUT"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Cleanup function
cleanup() {
    echo ""
    echo "Cleaning up test directory..."
    rm -rf "$TEST_DIR"
    echo "Done."
}

trap cleanup EXIT

# Check if memory-tool is available
if ! command -v memory-tool &> /dev/null; then
    echo -e "${RED}ERROR: memory-tool not found in PATH${NC}"
    echo "Please run scripts/install.sh first."
    exit 1
fi

# Initialize database
echo "Initializing test database..."
memory-tool --init > /dev/null 2>&1
echo ""

# Test 1: Database initialization
run_test "Database initialized" "test -f $TEST_DIR/memories.db"

# Test 2: Add memory
run_test "Add learning memory" "memory-tool add learning 'Test learning item'"

# Test 3: Add memory with project
run_test "Add memory with project" "memory-tool add decision 'Use PostgreSQL' --project TestApp"

# Test 4: Add memory with tags
run_test "Add memory with tags" "memory-tool add architecture 'Microservices architecture' --tags backend,api"

# Test 5: Add memory with priority
run_test "Add memory with priority" "memory-tool add pending 'Fix bug #123' --priority 9"

# Test 6: Search for memory
run_test_output "Search for memory" "memory-tool search 'PostgreSQL'" "Use PostgreSQL"

# Test 7: List memories
run_test_output "List all memories" "memory-tool list" "learning"

# Test 8: List by category
run_test_output "List by category" "memory-tool list --category decision" "PostgreSQL"

# Test 9: List by project
run_test_output "List by project" "memory-tool list --project TestApp" "PostgreSQL"

# Test 10: List pending items
run_test_output "List pending" "memory-tool pending" "Fix bug"

# Test 11: Update memory
MEM_ID=$(memory-tool search 'PostgreSQL' | grep -o 'ID: [0-9]*' | head -1 | cut -d' ' -f2)
run_test "Update memory" "memory-tool update $MEM_ID 'Use PostgreSQL 15 for better performance'"

# Test 12: Verify update
run_test_output "Verify update" "memory-tool search 'PostgreSQL 15'" "better performance"

# Test 13: Add related memory
MEM_ID2=$(memory-tool add decision 'Use connection pooling' --project TestApp | grep -o 'ID: [0-9]*' | cut -d' ' -f2)
run_test "Add relationship" "memory-tool relate $MEM_ID $MEM_ID2 related_to"

# Test 14: Add memory with expiry
FUTURE_DATE=$(date -d '+30 days' +%Y-%m-%d 2>/dev/null || date -v +30d +%Y-%m-%d 2>/dev/null || echo '2026-04-10')
run_test "Add memory with expiry" "memory-tool add pending 'Complete migration' --expires $FUTURE_DATE"

# Test 15: Stats command
run_test_output "Show statistics" "memory-tool stats" "Total memories"

# Test 16: Export MEMORY.md
run_test "Export MEMORY.md" "memory-tool export"

# Test 17: Verify export
run_test "MEMORY.md exists" "test -f $TEST_DIR/MEMORY.md"

# Test 18: Delete memory
run_test "Delete memory" "memory-tool delete $MEM_ID2"

# Test 19: Backup database
run_test "Backup database" "memory-tool backup"

# Test 20: Verify backup exists
run_test "Backup file exists" "ls $TEST_DIR/backups/*.db | head -1"

# Test 21: Decay command
run_test "Run decay" "memory-tool decay"

# Test 22: Graph - Add entity
run_test "Add graph entity" "memory-tool graph add-entity 'TestService' 'service' 'Test service description'"

# Test 23: Graph - Set fact
run_test "Set graph fact" "memory-tool graph set-fact 'TestService' 'port' '3000'"

# Test 24: Graph - Add relationship
run_test "Add graph entity 2" "memory-tool graph add-entity 'TestDB' 'database' 'Test database'"
run_test "Add graph relationship" "memory-tool graph add-relationship 'TestService' 'TestDB' 'depends_on'"

# Test 25: Graph - Get entity
run_test_output "Get graph entity" "memory-tool graph get 'TestService'" "TestService"

# Test 26: Graph - Spread activation
run_test_output "Graph spread" "memory-tool graph spread 'TestService' 2" "TestDB"

# Test 27: Search modes - keyword
run_test_output "Search keyword mode" "memory-tool search --mode keyword 'PostgreSQL'" "PostgreSQL"

# Test 28: Topics command
run_test "List topics" "memory-tool topics"

# Test 29: Add conflicting memory
memory-tool add decision 'Use MySQL instead' --project TestApp > /dev/null 2>&1
run_test "Detect conflicts" "memory-tool conflicts"

# Test 30: Snapshot command
run_test "Create snapshot" "memory-tool snapshot 'Test session summary'"

# Print summary
echo ""
echo "===================================="
echo -e "${GREEN}Test Results${NC}"
echo "===================================="
echo "Total tests: $TESTS_RUN"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "${RED}Failed: $TESTS_FAILED${NC}"
else
    echo "Failed: $TESTS_FAILED"
fi

# Calculate percentage
if [ $TESTS_RUN -gt 0 ]; then
    PERCENTAGE=$((TESTS_PASSED * 100 / TESTS_RUN))
    echo "Success rate: $PERCENTAGE%"
fi

echo ""

# Exit with appropriate code
if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
else
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
fi
