"""Mode profiles for different memory usage patterns."""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from .config import get_logger

logger = get_logger(__name__)

# Mode configurations
MODES = {
    "default": {
        "search_limit": 10,
        "auto_tag": True,
        "show_tokens": True,
        "focus_projects": None,
        "focus_categories": None,
    },
    "dev": {
        "search_limit": 15,
        "auto_tag": True,
        "show_tokens": True,
        "focus_projects": None,
        "focus_categories": None,
    },
    "ops": {
        "search_limit": 5,
        "auto_tag": True,
        "show_tokens": False,
        "focus_categories": ["error", "learning"],
        "focus_projects": None,
    },
    "research": {
        "search_limit": 20,
        "auto_tag": True,
        "show_tokens": True,
        "focus_projects": None,
        "focus_categories": None,
    },
    "monitor": {
        "search_limit": 3,
        "auto_tag": False,
        "show_tokens": False,
        "focus_categories": ["error", "pending"],
        "focus_projects": None,
    },
}


def get_mode_config_path() -> Path:
    """Get path to mode config file (next to the DB)."""
    from .config import DB_PATH
    return DB_PATH.parent / "mode_config.json"


def get_mode() -> str:
    """Get current mode from env var or config file."""
    # Check env var first
    env_mode = os.environ.get("AIIQ_MODE")
    if env_mode and env_mode in MODES:
        return env_mode

    # Check config file
    config_path = get_mode_config_path()
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
                mode = config.get("mode", "default")
                if mode in MODES:
                    return mode
        except (json.JSONDecodeError, IOError):
            pass

    return "default"


def set_mode(mode: str) -> bool:
    """Set mode in config file."""
    if mode not in MODES:
        logger.error(f"Unknown mode: {mode}. Valid modes: {', '.join(MODES.keys())}")
        return False

    config_path = get_mode_config_path()
    try:
        with open(config_path, "w") as f:
            json.dump({"mode": mode}, f)
        logger.info(f"Mode set to: {mode}")
        return True
    except IOError as e:
        logger.error(f"Failed to save mode config: {e}")
        return False


def get_mode_config() -> Dict[str, Any]:
    """Get merged config for current mode."""
    mode = get_mode()
    return MODES[mode].copy()


def list_modes() -> None:
    """Print all available modes with descriptions."""
    current = get_mode()

    descriptions = {
        "default": "Balanced settings for general use",
        "dev": "More search results, token tracking enabled",
        "ops": "Focused on errors and learnings, fewer results",
        "research": "Maximum search results for deep exploration",
        "monitor": "Minimal output, errors and pending items only",
    }

    print("Available modes:\n")
    for mode_name in MODES.keys():
        marker = " (current)" if mode_name == current else ""
        desc = descriptions.get(mode_name, "")
        config = MODES[mode_name]
        print(f"  {mode_name}{marker}")
        print(f"    {desc}")
        print(f"    search_limit={config['search_limit']}, show_tokens={config['show_tokens']}")
        if config.get("focus_categories"):
            print(f"    focus_categories={config['focus_categories']}")
        print()
