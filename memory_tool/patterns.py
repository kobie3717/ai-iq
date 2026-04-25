"""Cross-session pattern store for AI-IQ.

Accumulates adopt/avoid patterns from completed sessions so agents learn
from past runs. Inspired by harrymunro/nelson's cross-mission memory store.

Storage: same directory as memories.db → patterns.json
File-locked writes (fcntl) for concurrent safety.
"""

from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import MEMORY_DIR


PATTERNS_FILE: Path = Path(os.getenv("PATTERNS_FILE", str(MEMORY_DIR / "patterns.json")))


# ---------------------------------------------------------------------------
# File locking
# ---------------------------------------------------------------------------

@contextmanager
def _file_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_store(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "updated_at": None, "pattern_count": 0, "patterns": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "updated_at": None, "pattern_count": 0, "patterns": []}


def _write_store(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_session_id() -> str:
    import hashlib, time
    return hashlib.sha1(str(time.time()).encode()).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def add_pattern(
    adopt: Optional[str] = None,
    avoid: Optional[str] = None,
    context: str = "",
    session_id: Optional[str] = None,
) -> dict:
    """Append an adopt/avoid pattern from the current session.

    At least one of adopt or avoid must be provided.
    Returns the saved record.
    """
    if not adopt and not avoid:
        raise ValueError("At least one of adopt or avoid must be provided.")

    record = {
        "session_id": session_id or _generate_session_id(),
        "recorded_at": _now_iso(),
        "context": context,
        "adopt": [adopt] if adopt else [],
        "avoid": [avoid] if avoid else [],
    }

    lock_path = PATTERNS_FILE.parent / ".patterns.lock"
    with _file_lock(lock_path):
        store = _read_store(PATTERNS_FILE)
        patterns = list(store.get("patterns", []))
        patterns.append(record)
        store.update({
            "updated_at": _now_iso(),
            "pattern_count": len(patterns),
            "patterns": patterns,
        })
        _write_store(PATTERNS_FILE, store)

    return record


def list_patterns(last_n: int = 20) -> list[dict]:
    """Return most recent N patterns, newest first."""
    store = _read_store(PATTERNS_FILE)
    patterns = store.get("patterns", [])
    return list(reversed(patterns[-last_n:]))


def brief(context: str = "", top_n: int = 10) -> str:
    """Return a compact brief of relevant past patterns for prompt injection.

    Keyword-matches context string against pattern text.
    Returns formatted string ready for context injection.
    """
    store = _read_store(PATTERNS_FILE)
    patterns = store.get("patterns", [])

    if not patterns:
        return "No past patterns recorded yet."

    # Score each pattern by keyword overlap with context
    context_words = set(context.lower().split()) if context else set()

    def score(p: dict) -> int:
        text = " ".join(p.get("adopt", []) + p.get("avoid", []) + [p.get("context", "")])
        words = set(text.lower().split())
        return len(context_words & words) if context_words else 1

    scored = sorted(patterns, key=score, reverse=True)
    top = scored[:top_n]

    lines = ["📚 Past session patterns:"]
    for p in top:
        ctx = f" [{p['context']}]" if p.get("context") else ""
        date = p.get("recorded_at", "")[:10]
        for item in p.get("adopt", []):
            lines.append(f"  ✅ ADOPT ({date}){ctx}: {item}")
        for item in p.get("avoid", []):
            lines.append(f"  ❌ AVOID ({date}){ctx}: {item}")

    return "\n".join(lines)


def get_stats() -> dict:
    """Return aggregate stats across all recorded patterns."""
    store = _read_store(PATTERNS_FILE)
    patterns = store.get("patterns", [])

    all_adopt = [a for p in patterns for a in p.get("adopt", [])]
    all_avoid = [a for p in patterns for a in p.get("avoid", [])]

    # Find most common context keywords
    from collections import Counter
    ctx_words: list[str] = []
    for p in patterns:
        ctx_words.extend(p.get("context", "").lower().split())
    top_contexts = Counter(ctx_words).most_common(5)

    return {
        "total_sessions": len(patterns),
        "adopt_count": len(all_adopt),
        "avoid_count": len(all_avoid),
        "top_context_keywords": [w for w, _ in top_contexts],
        "last_recorded": patterns[-1]["recorded_at"] if patterns else None,
        "patterns_file": str(PATTERNS_FILE),
    }
