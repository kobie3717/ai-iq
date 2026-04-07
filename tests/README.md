# Test Suite

This directory contains test scripts for the AI-IQ system.

## Files

### test_basic.sh

Comprehensive test suite that validates core functionality in an isolated environment.

**Usage:**
```bash
bash tests/test_basic.sh
```

**What it tests:**

1. **Database Operations** (7 tests)
   - Database initialization
   - Add memories (simple, with project, tags, priority)
   - Search functionality
   - List operations (all, by category, by project)

2. **Memory Management** (8 tests)
   - Update memories
   - Delete memories
   - List pending items
   - Add relationships
   - Add memories with expiry dates
   - Statistics
   - Export to MEMORY.md
   - Backup/restore

3. **Maintenance** (2 tests)
   - Decay command
   - Garbage collection

4. **Knowledge Graph** (6 tests)
   - Add entities
   - Set facts
   - Add relationships
   - Get entity details
   - Spreading activation
   - Graph queries

5. **Advanced Features** (7 tests)
   - Search modes (keyword, semantic, hybrid)
   - Topics listing
   - Conflict detection
   - Snapshot creation
   - Session summaries
   - Merge operations

**Total: 30 tests**

## Features

- **Isolated Environment**: Uses temporary directory (`$TEMP_DIR`)
- **Safe**: No impact on your actual memories database
- **Comprehensive**: Tests all major features
- **Color Output**: Green for pass, red for fail
- **Summary Report**: Shows pass/fail count and percentage
- **Exit Codes**: Returns 0 if all pass, 1 if any fail

## Running Tests

### Basic run:
```bash
bash tests/test_basic.sh
```

### With verbose output:
```bash
bash tests/test_basic.sh 2>&1 | tee test-results.log
```

### Run from any directory:
```bash
cd /path/to/ai-iq
bash tests/test_basic.sh
```

## Expected Output

```
AI-IQ - Basic Test Suite
====================================
Test directory: /tmp/tmp.XXXXXXXXXX

Initializing test database...

Test 1: Database initialized... PASS
Test 2: Add learning memory... PASS
Test 3: Add memory with project... PASS
...
Test 30: Create snapshot... PASS

====================================
Test Results
====================================
Total tests: 30
Passed: 30
Failed: 0
Success rate: 100%

All tests passed!
```

## Troubleshooting

**memory-tool not found:**
- Install first: `bash scripts/install.sh`
- Ensure `~/.local/bin` is in PATH

**Some tests fail:**
- Check which tests failed
- Verify memory-tool.py has all features implemented
- Check if database is accessible
- Ensure Python dependencies are installed

**Permission denied:**
- Make executable: `chmod +x tests/test_basic.sh`

**Temp directory errors:**
- Ensure `/tmp` is writable
- Check disk space

## CI/CD Integration

Add to your CI pipeline:

**GitHub Actions:**
```yaml
- name: Run tests
  run: bash tests/test_basic.sh
```

**GitLab CI:**
```yaml
test:
  script:
    - bash tests/test_basic.sh
```

## Adding More Tests

To add new tests, edit `test_basic.sh` and use these helper functions:

```bash
# Test that expects success (exit code 0)
run_test "Test name" "command to run"

# Test that expects specific output
run_test_output "Test name" "command to run" "expected pattern"
```

Example:
```bash
run_test "Add priority memory" "memory-tool add pending 'Important task' --priority 10"
run_test_output "Search finds it" "memory-tool search 'Important'" "Important task"
```

## Future Tests

Planned additions:
- Integration tests with Claude Code hooks
- Performance tests (large database)
- Concurrent access tests
- Semantic search accuracy tests
- Graph traversal tests
- Import/export tests
- Backup/restore verification
- Edge case tests (special characters, long content, etc.)
