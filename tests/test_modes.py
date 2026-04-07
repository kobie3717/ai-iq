"""Tests for mode profiles."""

import pytest
import sys
import os
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_tool import modes
from memory_tool.config import DB_PATH


def test_default_mode(temp_db):
    """Test default mode is returned when nothing is set."""
    mode = modes.get_mode()
    assert mode == "default"


def test_get_mode_config_default(temp_db):
    """Test getting default mode config."""
    config = modes.get_mode_config()
    assert config["search_limit"] == 10
    assert config["auto_tag"] is True
    assert config["show_tokens"] is True


def test_set_mode_valid(temp_db):
    """Test setting a valid mode."""
    result = modes.set_mode("dev")
    assert result is True

    mode = modes.get_mode()
    assert mode == "dev"


def test_set_mode_invalid(temp_db):
    """Test setting an invalid mode."""
    result = modes.set_mode("nonexistent")
    assert result is False

    # Should still be default
    mode = modes.get_mode()
    assert mode == "default"


def test_mode_config_dev(temp_db):
    """Test dev mode config."""
    modes.set_mode("dev")
    config = modes.get_mode_config()
    assert config["search_limit"] == 15
    assert config["show_tokens"] is True


def test_mode_config_ops(temp_db):
    """Test ops mode config."""
    modes.set_mode("ops")
    config = modes.get_mode_config()
    assert config["search_limit"] == 5
    assert config["show_tokens"] is False
    assert "error" in config["focus_categories"]
    assert "learning" in config["focus_categories"]


def test_mode_config_research(temp_db):
    """Test research mode config."""
    modes.set_mode("research")
    config = modes.get_mode_config()
    assert config["search_limit"] == 20
    assert config["show_tokens"] is True


def test_mode_config_monitor(temp_db):
    """Test monitor mode config."""
    modes.set_mode("monitor")
    config = modes.get_mode_config()
    assert config["search_limit"] == 3
    assert config["show_tokens"] is False
    assert config["auto_tag"] is False
    assert "error" in config["focus_categories"]
    assert "pending" in config["focus_categories"]


def test_mode_env_var_override(temp_db):
    """Test that env var overrides config file."""
    # Set mode via file
    modes.set_mode("ops")

    # Set env var
    os.environ["AIIQ_MODE"] = "research"

    # Should return env var mode
    mode = modes.get_mode()
    assert mode == "research"

    # Clean up
    del os.environ["AIIQ_MODE"]


def test_mode_config_file_persistence(temp_db):
    """Test mode config persists in file."""
    config_path = modes.get_mode_config_path()

    # Set mode
    modes.set_mode("dev")

    # Check file exists and contains correct mode
    assert config_path.exists()
    with open(config_path, "r") as f:
        data = json.load(f)
        assert data["mode"] == "dev"


def test_all_modes_exist(temp_db):
    """Test all modes defined in MODES dict."""
    expected_modes = ["default", "dev", "ops", "research", "monitor"]
    for mode in expected_modes:
        assert mode in modes.MODES
        config = modes.MODES[mode]
        assert "search_limit" in config
        assert "auto_tag" in config
        assert "show_tokens" in config
