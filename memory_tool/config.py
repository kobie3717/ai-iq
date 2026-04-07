"""Configuration constants for memory-tool."""

import os
import logging
from pathlib import Path
from typing import Dict, List

# Paths
MEMORY_DIR: Path = Path(__file__).parent.parent
DB_PATH: Path = MEMORY_DIR / "memories.db"
MEMORY_MD_PATH: Path = MEMORY_DIR / "MEMORY.md"
TOPICS_DIR: Path = MEMORY_DIR / "topics"
BACKUP_DIR: Path = Path(os.getenv("MEMORY_BACKUP_DIR", str(Path.home() / "backups/memory")))
MAX_MEMORY_MD_BYTES: int = 5120  # 5KB hard cap

# OpenClaw Bridge paths (configurable via environment variables)
OPENCLAW_MEMORY_DIR: Path = Path(os.getenv("OPENCLAW_MEMORY_DIR", str(Path.home() / ".openclaw/workspace/memory")))
OPENCLAW_GRAPH_DB: Path = Path(os.getenv("OPENCLAW_GRAPH_DB", str(Path.home() / ".openclaw/memory-graph.db")))
SYNC_STATE_FILE: Path = MEMORY_DIR / ".sync-state.json"

# Staleness thresholds (days)
STALE_PENDING_DAYS: int = 30
STALE_GENERAL_DAYS: int = 90
DEPRIORITIZE_DAYS: int = 60

# Dedup similarity threshold (0.0 to 1.0)
SIMILARITY_THRESHOLD: float = 0.65

# Vector search configuration
MODEL_DIR: Path = Path.home() / ".cache/models/all-MiniLM-L6-v2"
EMBEDDING_DIM: int = 384
RRF_K: int = 60  # Reciprocal Rank Fusion constant

# Project detection paths (example - customize for your projects)
PROJECT_PATHS: Dict[str, str] = {
    # Example format:
    # "/path/to/project": "ProjectName",
    # "/home/user/myapp": "MyApp",
}

# Auto-Tag Keywords
AUTO_TAG_RULES: Dict[str, List[str]] = {
    "pm2": ["pm2"],
    "whatsapp": ["whatsapp", "baileys", "webhook", "meta dashboard", "waba"],
    "baileys": ["baileys", "qrcode-terminal"],
    "database": ["postgresql", "psql", "prisma", "sequelize", "migration", "schema"],
    "auth": ["jwt", "login", "password", "token", "auth", "bcrypt"],
    "nginx": ["nginx", "reverse proxy", "ssl", "certbot", "letsencrypt"],
    "docker": ["docker", "container", "dockerfile"],
    "payfast": ["payfast", "payment", "merchant"],
    "wireguard": ["wireguard", "wg0", "wg-quick", "wg show"],
    "dns": ["unbound", "dns", "resolve", "dig"],
    "esm": ["esm", "commonjs", "import", "require", "module"],
    "react": ["react", "vite", "tailwind", "frontend", "tsx", "jsx"],
    "api": ["endpoint", "route", "controller", "middleware", "express"],
}


def get_logger(name: str) -> logging.Logger:
    """Get a logger for the specified module."""
    return logging.getLogger(f"ai_iq.{name}")


# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'  # Keep output clean for CLI
)
