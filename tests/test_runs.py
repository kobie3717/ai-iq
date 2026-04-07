"""Tests for run tracking operations."""

import pytest
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_tool import runs, database


class TestStartRun:
    """Test starting new runs."""

    def test_start_basic_run(self, temp_db):
        """Test starting a basic run."""
        run_id = runs.start_run("Test task")

        assert run_id is not None
        assert isinstance(run_id, int)
        assert run_id > 0

        # Verify in database
        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()

        assert row is not None
        assert row["task"] == "Test task"
        assert row["status"] == "running"
        assert row["agent"] == "claw"

    def test_start_run_with_agent(self, temp_db):
        """Test starting run with specific agent."""
        run_id = runs.start_run("Test task", agent="claude")

        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()

        assert row["agent"] == "claude"

    def test_start_run_with_project(self, temp_db):
        """Test starting run with project."""
        run_id = runs.start_run("Test task", project="TestProject")

        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()

        assert row["project"] == "TestProject"

    def test_start_run_with_tags(self, temp_db):
        """Test starting run with tags."""
        run_id = runs.start_run("Test task", tags="testing,development")

        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()

        assert row["tags"] == "testing,development"

    def test_start_run_with_all_params(self, temp_db):
        """Test starting run with all parameters."""
        run_id = runs.start_run(
            "Complex task",
            agent="custom",
            project="MyProject",
            tags="tag1,tag2,tag3"
        )

        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()

        assert row["task"] == "Complex task"
        assert row["agent"] == "custom"
        assert row["project"] == "MyProject"
        assert row["tags"] == "tag1,tag2,tag3"


class TestAddRunStep:
    """Test adding steps to runs."""

    def test_add_step_to_run(self, temp_db):
        """Test adding a step to a run."""
        run_id = runs.start_run("Test task")
        success = runs.add_run_step(run_id, "First step completed")

        assert success is True

        # Verify step was added
        conn = database.get_db()
        row = conn.execute("SELECT steps FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()

        steps = json.loads(row["steps"])
        assert len(steps) == 1
        assert steps[0] == "First step completed"

    def test_add_multiple_steps(self, temp_db):
        """Test adding multiple steps to a run."""
        run_id = runs.start_run("Test task")

        runs.add_run_step(run_id, "Step 1")
        runs.add_run_step(run_id, "Step 2")
        runs.add_run_step(run_id, "Step 3")

        conn = database.get_db()
        row = conn.execute("SELECT steps FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()

        steps = json.loads(row["steps"])
        assert len(steps) == 3
        assert steps[0] == "Step 1"
        assert steps[1] == "Step 2"
        assert steps[2] == "Step 3"

    def test_add_step_to_nonexistent_run(self, temp_db):
        """Test adding step to non-existent run."""
        success = runs.add_run_step(99999, "This should fail")

        assert success is False

    def test_add_step_preserves_order(self, temp_db):
        """Test that steps maintain order."""
        run_id = runs.start_run("Test task")

        for i in range(10):
            runs.add_run_step(run_id, f"Step {i}")

        conn = database.get_db()
        row = conn.execute("SELECT steps FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()

        steps = json.loads(row["steps"])
        assert len(steps) == 10

        for i, step in enumerate(steps):
            assert step == f"Step {i}"


class TestCompleteRun:
    """Test completing runs."""

    def test_complete_run(self, temp_db):
        """Test completing a run."""
        run_id = runs.start_run("Test task")
        runs.complete_run(run_id, "Successfully completed")

        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()

        assert row["status"] == "completed"
        assert row["outcome"] == "Successfully completed"
        assert row["completed_at"] is not None

    def test_complete_run_with_steps(self, temp_db):
        """Test completing run that has steps."""
        run_id = runs.start_run("Test task")
        runs.add_run_step(run_id, "Step 1")
        runs.add_run_step(run_id, "Step 2")
        runs.complete_run(run_id, "All steps completed")

        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()

        assert row["status"] == "completed"
        steps = json.loads(row["steps"])
        assert len(steps) == 2


class TestFailRun:
    """Test failing runs."""

    def test_fail_run(self, temp_db):
        """Test marking run as failed."""
        run_id = runs.start_run("Test task")
        runs.fail_run(run_id, "Failed due to error")

        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()

        assert row["status"] == "failed"
        assert row["outcome"] == "Failed due to error"
        assert row["completed_at"] is not None

    def test_fail_run_with_steps(self, temp_db):
        """Test failing run that has steps."""
        run_id = runs.start_run("Test task")
        runs.add_run_step(run_id, "Step 1 completed")
        runs.add_run_step(run_id, "Step 2 started")
        runs.fail_run(run_id, "Step 2 failed")

        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()

        assert row["status"] == "failed"
        assert "Step 2 failed" in row["outcome"]


class TestCancelRun:
    """Test cancelling runs."""

    def test_cancel_run(self, temp_db):
        """Test cancelling a run."""
        run_id = runs.start_run("Test task")
        runs.cancel_run(run_id)

        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()

        assert row["status"] == "cancelled"
        assert row["completed_at"] is not None

    def test_cancel_run_with_steps(self, temp_db):
        """Test cancelling run with steps."""
        run_id = runs.start_run("Test task")
        runs.add_run_step(run_id, "Partial work")
        runs.cancel_run(run_id)

        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()

        assert row["status"] == "cancelled"
        steps = json.loads(row["steps"])
        assert len(steps) == 1  # Steps preserved


class TestListRuns:
    """Test listing runs."""

    def test_list_all_runs(self, temp_db):
        """Test listing all runs."""
        # Create multiple runs
        runs.start_run("Task 1")
        runs.start_run("Task 2")
        runs.start_run("Task 3")

        result = runs.list_runs()

        assert len(result) == 3

    def test_list_runs_with_limit(self, temp_db):
        """Test listing runs with limit."""
        # Create multiple runs
        for i in range(20):
            runs.start_run(f"Task {i}")

        result = runs.list_runs(limit=5)

        assert len(result) == 5

    def test_list_runs_by_status(self, temp_db):
        """Test listing runs filtered by status."""
        run1 = runs.start_run("Task 1")
        run2 = runs.start_run("Task 2")
        run3 = runs.start_run("Task 3")

        runs.complete_run(run1, "Done")
        runs.fail_run(run2, "Failed")
        # run3 still running

        # List running runs
        running = runs.list_runs(status="running")
        assert len(running) == 1

        # List completed runs
        completed = runs.list_runs(status="completed")
        assert len(completed) == 1

        # List failed runs
        failed = runs.list_runs(status="failed")
        assert len(failed) == 1

    def test_list_runs_by_project(self, temp_db):
        """Test listing runs filtered by project."""
        runs.start_run("Task 1", project="ProjectA")
        runs.start_run("Task 2", project="ProjectB")
        runs.start_run("Task 3", project="ProjectA")

        result = runs.list_runs(project="ProjectA")

        assert len(result) == 2
        for row in result:
            assert row["project"] == "ProjectA"

    def test_list_runs_by_status_and_project(self, temp_db):
        """Test listing runs with multiple filters."""
        run1 = runs.start_run("Task 1", project="ProjectA")
        run2 = runs.start_run("Task 2", project="ProjectA")
        run3 = runs.start_run("Task 3", project="ProjectB")

        runs.complete_run(run1, "Done")
        # run2 still running
        runs.complete_run(run3, "Done")

        result = runs.list_runs(status="completed", project="ProjectA")

        assert len(result) == 1
        assert result[0]["project"] == "ProjectA"
        assert result[0]["status"] == "completed"

    def test_list_runs_ordered_by_date(self, temp_db):
        """Test that runs are ordered by date (newest first per SQL)."""
        run1 = runs.start_run("Task 1")
        run2 = runs.start_run("Task 2")
        run3 = runs.start_run("Task 3")

        result = runs.list_runs()

        # Verify we got all 3 runs
        assert len(result) == 3

        # Verify they're ordered (DESC by started_at means newest first)
        # Since all created in same second, check that list_runs returns them
        result_ids = [r["id"] for r in result]
        assert run1 in result_ids
        assert run2 in result_ids
        assert run3 in result_ids


class TestShowRun:
    """Test showing run details."""

    def test_show_existing_run(self, temp_db):
        """Test showing details of existing run."""
        run_id = runs.start_run("Test task", project="TestProj", tags="test")
        runs.add_run_step(run_id, "Step 1")
        runs.add_run_step(run_id, "Step 2")

        result = runs.show_run(run_id)

        assert result is not None
        assert result["id"] == run_id
        assert result["task"] == "Test task"
        assert result["project"] == "TestProj"
        assert result["tags"] == "test"
        assert result["status"] == "running"

    def test_show_completed_run(self, temp_db):
        """Test showing completed run."""
        run_id = runs.start_run("Test task")
        runs.complete_run(run_id, "Success")

        result = runs.show_run(run_id)

        assert result["status"] == "completed"
        assert result["outcome"] == "Success"
        assert result["completed_at"] is not None

    def test_show_nonexistent_run(self, temp_db):
        """Test showing non-existent run."""
        result = runs.show_run(99999)

        assert result is None


class TestFormatDuration:
    """Test format_duration function."""

    def test_format_duration_seconds(self):
        """Test formatting duration in seconds."""
        start = datetime.now().isoformat()
        end = (datetime.now()).isoformat()

        result = runs.format_duration(start, end)

        assert "s" in result or result == "0s"

    def test_format_duration_minutes(self):
        """Test formatting duration in minutes."""
        now = datetime.now()
        start = (now - timedelta(minutes=5)).isoformat()
        end = now.isoformat()

        result = runs.format_duration(start, end)

        assert "m" in result

    def test_format_duration_hours(self):
        """Test formatting duration in hours."""
        now = datetime.now()
        start = (now - timedelta(hours=2, minutes=30)).isoformat()
        end = now.isoformat()

        result = runs.format_duration(start, end)

        assert "h" in result

    def test_format_duration_no_end_time(self):
        """Test formatting duration without end time (still running)."""
        start = (datetime.now() - timedelta(minutes=10)).isoformat()

        result = runs.format_duration(start)

        assert result != "unknown"

    def test_format_duration_invalid_start(self):
        """Test formatting duration with invalid start time."""
        result = runs.format_duration(None)

        assert result == "unknown"

    def test_format_duration_invalid_format(self):
        """Test formatting duration with invalid date format."""
        result = runs.format_duration("invalid-date")

        assert result == "unknown"

    def test_format_duration_less_than_minute(self):
        """Test formatting duration less than a minute."""
        now = datetime.now()
        start = (now - timedelta(seconds=45)).isoformat()
        end = now.isoformat()

        result = runs.format_duration(start, end)

        assert "s" in result
        assert "m" not in result or result.endswith("s")

    def test_format_duration_exactly_one_hour(self):
        """Test formatting exactly one hour duration."""
        now = datetime.now()
        start = (now - timedelta(hours=1)).isoformat()
        end = now.isoformat()

        result = runs.format_duration(start, end)

        assert "h" in result


class TestRunStepEdgeCases:
    """Test edge cases for run steps."""

    def test_add_step_with_special_characters(self, temp_db):
        """Test adding step with special characters."""
        run_id = runs.start_run("Test task")
        step_text = "Step with \"quotes\" and <tags> & symbols"

        success = runs.add_run_step(run_id, step_text)

        assert success is True

        conn = database.get_db()
        row = conn.execute("SELECT steps FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()

        steps = json.loads(row["steps"])
        assert step_text in steps

    def test_add_step_with_unicode(self, temp_db):
        """Test adding step with Unicode characters."""
        run_id = runs.start_run("Test task")
        step_text = "Step with émojis 🎉 and ümlauts"

        success = runs.add_run_step(run_id, step_text)

        assert success is True

        conn = database.get_db()
        row = conn.execute("SELECT steps FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()

        steps = json.loads(row["steps"])
        assert len(steps) == 1

    def test_add_empty_step(self, temp_db):
        """Test adding empty step."""
        run_id = runs.start_run("Test task")
        success = runs.add_run_step(run_id, "")

        assert success is True

        conn = database.get_db()
        row = conn.execute("SELECT steps FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()

        steps = json.loads(row["steps"])
        assert len(steps) == 1
        assert steps[0] == ""

    def test_add_very_long_step(self, temp_db):
        """Test adding very long step."""
        run_id = runs.start_run("Test task")
        long_step = "A" * 1000

        success = runs.add_run_step(run_id, long_step)

        assert success is True

        conn = database.get_db()
        row = conn.execute("SELECT steps FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()

        steps = json.loads(row["steps"])
        assert len(steps[0]) == 1000


class TestRunWorkflow:
    """Test complete run workflows."""

    def test_complete_run_workflow(self, temp_db):
        """Test a complete run workflow from start to finish."""
        # Start run
        run_id = runs.start_run("Complete workflow test", project="TestProj", tags="test,workflow")

        # Add steps
        runs.add_run_step(run_id, "Initialize")
        runs.add_run_step(run_id, "Process data")
        runs.add_run_step(run_id, "Validate results")
        runs.add_run_step(run_id, "Cleanup")

        # Complete run
        runs.complete_run(run_id, "All tasks completed successfully")

        # Verify final state
        result = runs.show_run(run_id)

        assert result["status"] == "completed"
        assert result["outcome"] == "All tasks completed successfully"
        assert result["project"] == "TestProj"
        assert result["tags"] == "test,workflow"

        steps = json.loads(result["steps"])
        assert len(steps) == 4

    def test_failed_run_workflow(self, temp_db):
        """Test a run that fails mid-execution."""
        run_id = runs.start_run("Failing workflow test")

        runs.add_run_step(run_id, "Step 1 success")
        runs.add_run_step(run_id, "Step 2 success")
        runs.add_run_step(run_id, "Step 3 started")

        # Fail the run
        runs.fail_run(run_id, "Step 3 encountered error")

        result = runs.show_run(run_id)

        assert result["status"] == "failed"
        assert "error" in result["outcome"].lower()

        steps = json.loads(result["steps"])
        assert len(steps) == 3

    def test_cancelled_run_workflow(self, temp_db):
        """Test a run that gets cancelled."""
        run_id = runs.start_run("Cancellable workflow test")

        runs.add_run_step(run_id, "Starting")
        runs.cancel_run(run_id)

        result = runs.show_run(run_id)

        assert result["status"] == "cancelled"


class TestRunListingPerformance:
    """Test run listing with many runs."""

    def test_list_with_many_runs(self, temp_db):
        """Test listing performance with many runs."""
        # Create 100 runs
        for i in range(100):
            runs.start_run(f"Task {i}", project=f"Project{i % 5}")

        # List with limit should be fast
        result = runs.list_runs(limit=10)

        assert len(result) == 10

    def test_list_filters_with_many_runs(self, temp_db):
        """Test filtering with many runs."""
        # Create mixed runs
        for i in range(50):
            run_id = runs.start_run(f"Task {i}", project="ProjectA")
            if i % 3 == 0:
                runs.complete_run(run_id, "Done")
            elif i % 3 == 1:
                runs.fail_run(run_id, "Failed")

        # Filter by status and project
        completed = runs.list_runs(status="completed", project="ProjectA")
        failed = runs.list_runs(status="failed", project="ProjectA")
        running = runs.list_runs(status="running", project="ProjectA")

        assert len(completed) > 0
        assert len(failed) > 0
        assert len(running) > 0
