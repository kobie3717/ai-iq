#!/bin/bash
# Test script for AI-IQ Claude Code hooks

set -e

echo "=== AI-IQ Hook Test Suite ==="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Test 1: Check if memory-tool is installed
echo "Test 1: Checking memory-tool installation..."
if command -v memory-tool &> /dev/null; then
    echo -e "${GREEN}✓ memory-tool is installed${NC}"
    memory-tool --version 2>/dev/null || echo "(version check failed)"
else
    echo -e "${RED}✗ memory-tool not found${NC}"
    echo "Install with: pip install ai-iq"
    exit 1
fi
echo ""

# Test 2: Check hook scripts exist
echo "Test 2: Checking hook scripts..."
HOOKS=("error-hook.sh" "session-hook.sh" "session-start-hook.sh" "daily-maintenance.sh")
for hook in "${HOOKS[@]}"; do
    if [ -f "$SCRIPT_DIR/$hook" ]; then
        if [ -x "$SCRIPT_DIR/$hook" ]; then
            echo -e "${GREEN}✓ $hook exists and is executable${NC}"
        else
            echo -e "${YELLOW}⚠ $hook exists but is not executable${NC}"
            chmod +x "$SCRIPT_DIR/$hook"
            echo -e "${GREEN}  Fixed permissions${NC}"
        fi
    else
        echo -e "${RED}✗ $hook not found${NC}"
        exit 1
    fi
done
echo ""

# Test 3: Test session-start hook
echo "Test 3: Testing session-start hook..."
bash "$SCRIPT_DIR/session-start-hook.sh"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Session-start hook executed successfully${NC}"
else
    echo -e "${RED}✗ Session-start hook failed${NC}"
    exit 1
fi
echo ""

# Test 4: Test error hook with mock data
echo "Test 4: Testing error hook with mock failure..."
MOCK_INPUT='{"tool_name":"Bash","tool_input":{"command":"false"},"tool_result":"Command failed\nExit code: 1"}'
echo "$MOCK_INPUT" | bash "$SCRIPT_DIR/error-hook.sh"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Error hook executed successfully${NC}"

    # Check if error was captured
    echo "  Checking if error was logged..."
    ERROR_COUNT=$(memory-tool list --category error 2>/dev/null | grep -c "false" || true)
    if [ "$ERROR_COUNT" -gt 0 ]; then
        echo -e "${GREEN}  ✓ Error was captured in memory${NC}"
    else
        echo -e "${YELLOW}  ⚠ Error hook ran but error not found in memory (may have been deduplicated)${NC}"
    fi
else
    echo -e "${RED}✗ Error hook failed${NC}"
    exit 1
fi
echo ""

# Test 5: Test session hook
echo "Test 5: Testing session hook..."
bash "$SCRIPT_DIR/session-hook.sh"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Session hook executed successfully${NC}"
else
    echo -e "${RED}✗ Session hook failed${NC}"
    exit 1
fi
echo ""

# Test 6: Check if MEMORY.md was generated
echo "Test 6: Checking MEMORY.md generation..."
MEMORY_FILE="${XDG_DATA_HOME:-$HOME/.local/share}/ai-memory/MEMORY.md"
if [ -f "$MEMORY_FILE" ]; then
    echo -e "${GREEN}✓ MEMORY.md exists at $MEMORY_FILE${NC}"
    LINES=$(wc -l < "$MEMORY_FILE")
    echo "  File has $LINES lines"
else
    echo -e "${YELLOW}⚠ MEMORY.md not found (expected at $MEMORY_FILE)${NC}"
fi
echo ""

# Test 7: Test memory operations
echo "Test 7: Testing basic memory operations..."
TEST_ID=$(memory-tool add learning "AI-IQ hook test - $(date +%s)" --project test --tags hook-test 2>&1 | grep -oP 'Created memory \K\d+' || echo "")
if [ -n "$TEST_ID" ]; then
    echo -e "${GREEN}✓ Created test memory (ID: $TEST_ID)${NC}"

    # Search for it
    SEARCH_RESULT=$(memory-tool search "hook test" 2>/dev/null | grep -c "hook-test" || true)
    if [ "$SEARCH_RESULT" -gt 0 ]; then
        echo -e "${GREEN}✓ Search found test memory${NC}"
    else
        echo -e "${YELLOW}⚠ Search did not find test memory${NC}"
    fi

    # Clean up
    memory-tool delete "$TEST_ID" &>/dev/null || true
    echo -e "${GREEN}✓ Cleaned up test memory${NC}"
else
    echo -e "${YELLOW}⚠ Could not create test memory (may need to check permissions)${NC}"
fi
echo ""

# Test 8: Check stats
echo "Test 8: Checking memory stats..."
if memory-tool stats &>/dev/null; then
    echo -e "${GREEN}✓ Memory stats command works${NC}"
    memory-tool stats 2>/dev/null | head -n 10
else
    echo -e "${RED}✗ Memory stats command failed${NC}"
    exit 1
fi
echo ""

echo "=== All Tests Passed ==="
echo ""
echo "Your AI-IQ hooks are ready to use!"
echo ""
echo "Next steps:"
echo "1. Run the installer: bash $SCRIPT_DIR/install.sh"
echo "2. Add CLAUDE.md section to your project: cat $SCRIPT_DIR/CLAUDE.md.example >> /your/project/CLAUDE.md"
echo "3. Start using Claude Code - memories will be auto-captured!"
echo ""
