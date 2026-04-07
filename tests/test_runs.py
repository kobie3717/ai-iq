"""Tests for run tracking functionality."""

import pytest
import sys
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_tool import runs, database, cli


class TestStartRun:
    """Test starting runs."""

    def test_start_run_basic(self, temp_db):
        """Test starting a basic run."""
        run_id = runs.start_run("Test task", agent="claw")

        assert run_id is not None
        assert run_id > 0

        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        assert row is not None
        assert row['task'] == "Test task"
        assert row['agent'] == "claw"
        assert row['status'] == "running"
        conn.close()

    def test_start_run_with_project(self, temp_db):
        """Test starting run with project."""
        run_id = runs.start_run("Task with project", agent="claude", project="FlashVault")

        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        assert row['project'] == "FlashVault"
        conn.close()

    def test_start_run_with_tags(self, temp_db):
        """Test starting run with tags."""
        run_id = runs.start_run("Tagged task", tags="testing,integration")

        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        assert row['tags'] == "testing,integration"
        conn.close()

    def test_start_run_default_agent(self, temp_db):
        """Test default agent is 'claw'."""
        run_id = runs.start_run("Task with default agent")

        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        assert row['agent'] == "claw"
        conn.close()


class TestAddRunStep:
    """Test adding steps to runs."""

    def test_add_run_step(self, temp_db):
        """Test adding a step to a run."""
        run_id = runs.start_run("Task with steps")
        success = runs.add_run_step(run_id, "First step completed")

        assert success is True

        conn = database.get_db()
        row = conn.execute("SELECT steps FROM runs WHERE id = ?", (run_id,)).fetchone()
        steps = json.loads(row['steps'])
        assert len(steps) == 1
        assert steps[0] == "First step completed"
        conn.close()

    def test_add_multiple_steps(self, temp_db):
        """Test adding multiple steps."""
        run_id = runs.start_run("Multi-step task")

        runs.add_run_step(run_id, "Step 1")
        runs.add_run_step(run_id, "Step 2")
        runs.add_run_step(run_id, "Step 3")

        conn = database.get_db()
        row = conn.execute("SELECT steps FROM runs WHERE id = ?", (run_id,)).fetchone()
        steps = json.loads(row['steps'])
        assert len(steps) == 3
        assert steps[0] == "Step 1"
        assert steps[1] == "Step 2"
        assert steps[2] == "Step 3"
        conn.close()

    def test_add_step_to_nonexistent_run(self, temp_db):
        """Test adding step to non-existent run fails."""
        success = runs.add_run_step(9999, "Should fail")
        assert success is False


class TestCompleteRun:
    """Test completing runs."""

    def test_complete_run(self, temp_db):
        """Test completing a run."""
        run_id = runs.start_run("Task to complete")
        runs.complete_run(run_id, "Successfully completed task")

        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        assert row['status'] == "completed"
        assert row['outcome'] == "Successfully completed task"
        assert row['completed_at'] is not None
        conn.close()

    def test_complete_run_updates_timestamp(self, temp_db):
        """Test completing run sets completed_at."""
        run_id = runs.start_run("Task to complete")

        conn = database.get_db()
        row_before = conn.execute("SELECT completed_at FROM runs WHERE id = ?", (run_id,)).fetchone()
        assert row_before['completed_at'] is None
        conn.close()

        runs.complete_run(run_id, "Done")

        conn = database.get_db()
        row_after = conn.execute("SELECT completed_at FROM runs WHERE id = ?", (run_id,)).fetchone()
        assert row_after['completed_at'] is not None
        conn.close()


class TestFailRun:
    """Test failing runs."""

    def test_fail_run(self, temp_db):
        """Test failing a run."""
        run_id = runs.start_run("Task that fails")
        runs.fail_run(run_id, "Error occurred during execution")

        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        assert row['status'] == "failed"
        assert row['outcome'] == "Error occurred during execution"
        assert row['completed_at'] is not None
        conn.close()


class TestCancelRun:
    """Test canceling runs."""

    def test_cancel_run(self, temp_db):
        """Test canceling a run."""
        run_id = runs.start_run("Task to cancel")
        runs.cancel_run(run_id)

        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        assert row['status'] == "cancelled"
        assert row['completed_at'] is not None
        conn.close()


class TestListRuns:
    """Test listing runs."""

    def test_list_runs_all(self, temp_db):
        """Test listing all runs."""
        # Create multiple runs
        runs.start_run("Task 1", agent="claw")
        runs.start_run("Task 2", agent="claude")
        runs.start_run("Task 3", agent="claw")

        result = runs.list_runs(limit=10)
        assert len(result) == 3

    def test_list_runs_filter_by_status(self, temp_db):
        """Test filtering runs by status."""
        run1 = runs.start_run("Running task")
        run2 = runs.start_run("Completed task")
        runs.complete_run(run2, "Done")
        run3 = runs.start_run("Failed task")
        runs.fail_run(run3, "Error")

        # Get only running
        running = runs.list_runs(status="running", limit=10)
        assert len(running) == 1
        assert running[0]['id'] == run1

        # Get only completed
        completed = runs.list_runs(status="completed", limit=10)
        assert len(completed) == 1
        assert completed[0]['id'] == run2

        # Get only failed
        failed = runs.list_runs(status="failed", limit=10)
        assert len(failed) == 1
        assert failed[0]['id'] == run3

    def test_list_runs_filter_by_project(self, temp_db):
        """Test filtering runs by project."""
        runs.start_run("Task A", project="ProjectX")
        runs.start_run("Task B", project="ProjectY")
        runs.start_run("Task C", project="ProjectX")

        result = runs.list_runs(project="ProjectX", limit=10)
        assert len(result) == 2

    def test_list_runs_with_limit(self, temp_db):
        """Test limit parameter."""
        for i in range(10):
            runs.start_run(f"Task {i}")

        result = runs.list_runs(limit=5)
        assert len(result) == 5

    def test_list_runs_ordered_by_started_at(self, temp_db):
        """Test runs are ordered by started_at DESC, id DESC."""
        run1 = runs.start_run("First task")
        run2 = runs.start_run("Second task")
        run3 = runs.start_run("Third task")

        result = runs.list_runs(limit=10)

        # Most recent first (ordered by started_at DESC, then id DESC as tiebreaker)
        assert result[0]['id'] == run3
        assert result[1]['id'] == run2
        assert result[2]['id'] == run1


class TestShowRun:
    """Test showing run details."""

    def test_show_run(self, temp_db):
        """Test showing a single run."""
        run_id = runs.start_run("Task to show", agent="claude", project="TestProj")
        runs.add_run_step(run_id, "Step 1")
        runs.add_run_step(run_id, "Step 2")

        run = runs.show_run(run_id)

        assert run is not None
        assert run['id'] == run_id
        assert run['task'] == "Task to show"
        assert run['agent'] == "claude"
        assert run['project'] == "TestProj"
        assert run['status'] == "running"

    def test_show_run_nonexistent(self, temp_db):
        """Test showing non-existent run returns None."""
        run = runs.show_run(9999)
        assert run is None


class TestRunCLICommands:
    """Test run commands via CLI."""

    def test_run_start_cli(self, temp_db, monkeypatch, capsys):
        """Test 'run start' command."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'run', 'start', 'CLI task'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert "Started run" in captured.out

        # Verify in database
        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
        assert row['task'] == "CLI task"
        conn.close()

    def test_run_start_with_flags(self, temp_db, monkeypatch, capsys):
        """Test 'run start' with flags."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'run', 'start', 'Task with flags',
            '--agent', 'claude',
            '--project', 'TestProj',
            '--tags', 'test,cli'
        ])

        cli.main()

        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
        assert row['agent'] == 'claude'
        assert row['project'] == 'TestProj'
        assert row['tags'] == 'test,cli'
        conn.close()

    def test_run_step_cli(self, temp_db, monkeypatch, capsys):
        """Test 'run step' command."""
        run_id = runs.start_run("Task for steps")

        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'run', 'step', str(run_id), 'CLI step added'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert "Added step" in captured.out

        conn = database.get_db()
        row = conn.execute("SELECT steps FROM runs WHERE id = ?", (run_id,)).fetchone()
        steps = json.loads(row['steps'])
        assert len(steps) == 1
        assert steps[0] == "CLI step added"
        conn.close()

    def test_run_complete_cli(self, temp_db, monkeypatch, capsys):
        """Test 'run complete' command."""
        run_id = runs.start_run("Task to complete via CLI")

        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'run', 'complete', str(run_id), 'Completed successfully'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert "Completed run" in captured.out

        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        assert row['status'] == 'completed'
        assert row['outcome'] == 'Completed successfully'
        conn.close()

    def test_run_fail_cli(self, temp_db, monkeypatch, capsys):
        """Test 'run fail' command."""
        run_id = runs.start_run("Task to fail via CLI")

        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'run', 'fail', str(run_id), 'Failed due to error'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert "Failed run" in captured.out

        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        assert row['status'] == 'failed'
        assert row['outcome'] == 'Failed due to error'
        conn.close()

    def test_run_cancel_cli(self, temp_db, monkeypatch, capsys):
        """Test 'run cancel' command."""
        run_id = runs.start_run("Task to cancel via CLI")

        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'run', 'cancel', str(run_id)
        ])

        cli.main()

        captured = capsys.readouterr()
        assert "Cancelled run" in captured.out

        conn = database.get_db()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        assert row['status'] == 'cancelled'
        conn.close()

    def test_run_list_cli(self, temp_db, monkeypatch, capsys):
        """Test 'run list' command."""
        runs.start_run("Task 1")
        runs.start_run("Task 2")

        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'run', 'list'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert "Task 1" in captured.out or "Task 2" in captured.out
        assert "runs)" in captured.out or "ID" in captured.out

    def test_run_list_with_filters(self, temp_db, monkeypatch, capsys):
        """Test 'run list' with filters."""
        run1 = runs.start_run("Running task", project="ProjectX")
        run2 = runs.start_run("Completed task", project="ProjectX")
        runs.complete_run(run2, "Done")

        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'run', 'list',
            '--status', 'running',
            '--project', 'ProjectX',
            '--limit', '5'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert "Running task" in captured.out

    def test_run_show_cli(self, temp_db, monkeypatch, capsys):
        """Test 'run show' command."""
        run_id = runs.start_run("Detailed task", agent="claude", project="TestProj")
        runs.add_run_step(run_id, "Step 1")
        runs.add_run_step(run_id, "Step 2")

        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'run', 'show', str(run_id)
        ])

        cli.main()

        captured = capsys.readouterr()
        assert f"=== Run #{run_id} ===" in captured.out
        assert "Detailed task" in captured.out
        assert "claude" in captured.out
        assert "TestProj" in captured.out
        assert "Step 1" in captured.out
        assert "Step 2" in captured.out

    def test_run_show_nonexistent(self, temp_db, monkeypatch, capsys):
        """Test 'run show' with non-existent ID."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'run', 'show', '9999'
        ])

        cli.main()

        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_run_no_subcommand(self, temp_db, monkeypatch):
        """Test 'run' without subcommand shows usage."""
        monkeypatch.setattr(sys, 'argv', [
            'memory-tool', 'run'
        ])

        with pytest.raises(SystemExit):
            cli.main()


class TestFormatDuration:
    """Test duration formatting in detail."""

    def test_format_duration_edge_cases(self):
        """Test edge cases in duration formatting."""
        # Exactly 1 minute
        start = "2026-03-30T10:00:00"
        end = "2026-03-30T10:01:00"
        result = runs.format_duration(start, end)
        assert "1m" in result and "0s" in result

        # Exactly 1 hour
        start = "2026-03-30T10:00:00"
        end = "2026-03-30T11:00:00"
        result = runs.format_duration(start, end)
        assert "1h" in result and "0m" in result

    def test_format_duration_with_timezone(self):
        """Test duration with timezone markers."""
        start = "2026-03-30T10:00:00Z"
        end = "2026-03-30T10:05:30Z"
        result = runs.format_duration(start, end)
        assert "5m" in result and "30s" in result


class TestRunWorkflow:
    """Test complete run workflow."""

    def test_complete_run_workflow(self, temp_db):
        """Test a complete run workflow from start to finish."""
        # Start a run
        run_id = runs.start_run(
            "Complete workflow test",
            agent="claude",
            project="TestProject",
            tags="integration,test"
        )
        assert run_id > 0

        # Add steps
        runs.add_run_step(run_id, "Step 1: Initialize")
        runs.add_run_step(run_id, "Step 2: Process")
        runs.add_run_step(run_id, "Step 3: Finalize")

        # Complete the run
        runs.complete_run(run_id, "All steps completed successfully")

        # Verify final state
        run = runs.show_run(run_id)
        assert run['status'] == 'completed'
        assert run['outcome'] == 'All steps completed successfully'
        assert run['completed_at'] is not None

        steps = json.loads(run['steps'])
        assert len(steps) == 3
        assert steps[0] == "Step 1: Initialize"
        assert steps[1] == "Step 2: Process"
        assert steps[2] == "Step 3: Finalize"

    def test_failed_run_workflow(self, temp_db):
        """Test a failed run workflow."""
        run_id = runs.start_run("Task that will fail")

        runs.add_run_step(run_id, "Step 1: Started")
        runs.add_run_step(run_id, "Step 2: Error encountered")

        runs.fail_run(run_id, "Database connection failed")

        run = runs.show_run(run_id)
        assert run['status'] == 'failed'
        assert 'Database connection failed' in run['outcome']

    def test_cancelled_run_workflow(self, temp_db):
        """Test a cancelled run workflow."""
        run_id = runs.start_run("Task to be cancelled")

        runs.add_run_step(run_id, "Step 1: Started")
        runs.cancel_run(run_id)

        run = runs.show_run(run_id)
        assert run['status'] == 'cancelled'
        assert run['completed_at'] is not None
