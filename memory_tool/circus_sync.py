"""Circus Memory Commons sync integration for AI-IQ.

Enables write-through publishing of memories to Circus and
receiving memories from goal subscriptions via SSE.
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Optional

import requests


class CircusSync:
    """Manages sync with Circus Memory Commons."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.circus_url = os.getenv("CIRCUS_URL", "http://localhost:6200")
        self.agent_token = os.getenv("CIRCUS_AGENT_TOKEN", "")
        self.auto_publish = os.getenv("CIRCUS_AUTO_PUBLISH", "true").lower() == "true"

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_headers(self) -> dict:
        """Get HTTP headers with auth token."""
        return {
            "Authorization": f"Bearer {self.agent_token}",
            "Content-Type": "application/json"
        }

    def ensure_tables(self) -> None:
        """Ensure circus sync tables exist."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS circus_sync_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                local_circus_url TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                last_push_at TEXT,
                last_pull_at TEXT,
                pending_push_count INTEGER DEFAULT 0,
                is_connected INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS circus_memory_map (
                local_memory_id INTEGER NOT NULL,
                circus_memory_id TEXT NOT NULL,
                synced_at TEXT NOT NULL,
                PRIMARY KEY (local_memory_id, circus_memory_id)
            )
        """)

        conn.commit()
        conn.close()

    def is_connected(self) -> bool:
        """Check if connected to Circus."""
        return bool(self.circus_url and self.agent_token)

    def publish_memory(
        self,
        memory_id: int,
        content: str,
        category: str,
        tags: Optional[list[str]] = None,
        confidence: float = 0.9,
        privacy_tier: str = "team"
    ) -> Optional[str]:
        """
        Publish a memory to Circus.

        Returns circus_memory_id if successful, None otherwise.
        """
        if not self.is_connected():
            return None

        payload = {
            "content": content,
            "category": category,
            "tags": tags or [],
            "confidence": confidence,
            "privacy_tier": privacy_tier
        }

        try:
            response = requests.post(
                f"{self.circus_url}/api/v1/memory-commons/publish",
                headers=self._get_headers(),
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                circus_memory_id = data.get("memory_id")

                # Record mapping
                conn = self._get_conn()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO circus_memory_map
                    (local_memory_id, circus_memory_id, synced_at)
                    VALUES (?, ?, ?)
                """, (memory_id, circus_memory_id, datetime.utcnow().isoformat()))
                conn.commit()
                conn.close()

                return circus_memory_id
            else:
                return None

        except Exception as e:
            # Log sync failures at WARNING level (sanitized, no tokens/content)
            import logging
            logging.warning(
                "Circus sync failed for memory %s: %s",
                str(memory_id)[:16] if memory_id else "unknown",
                type(e).__name__,
            )
            return None

    def auto_publish_on_add(
        self,
        memory_id: int,
        content: str,
        category: str,
        tags: str = "",
        confidence: float = 0.9
    ) -> None:
        """
        Auto-publish hook called after memory add.

        This is the write-through integration point.
        """
        if not self.auto_publish or not self.is_connected():
            return

        # Skip certain categories
        skip_categories = ["pending", "error"]
        if category in skip_categories:
            return

        # Parse tags
        tag_list = []
        if tags:
            try:
                tag_list = json.loads(tags) if tags.startswith("[") else tags.split(",")
            except json.JSONDecodeError:
                tag_list = tags.split(",") if tags else []

        # Privacy tier default: team (same-owner bots share by default)
        privacy_tier = "team"

        # Determine privacy from tags
        if "private" in tag_list:
            privacy_tier = "private"
        elif "public" in tag_list:
            privacy_tier = "public"

        self.publish_memory(
            memory_id=memory_id,
            content=content,
            category=category,
            tags=tag_list,
            confidence=confidence,
            privacy_tier=privacy_tier
        )


def init_circus_sync(db_path: str) -> CircusSync:
    """Initialize Circus sync and ensure tables exist."""
    sync = CircusSync(db_path)
    sync.ensure_tables()
    return sync
