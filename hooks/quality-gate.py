#!/usr/bin/env python3
"""
AI-IQ Quality Gate Hook.

Reads Claude Code hook payload from stdin (JSON).
Checks for validation evidence in task output/description.
Exits 0 to allow, 2 to block with feedback on stderr.

Inspired by harrymunro/nelson's risk-tiered quality gates.

Usage in hooks.json (TaskCompleted event):
  python3 quality-gate.py

Risk tiers (set AI_IQ_RISK_TIER env var, default 0):
  0 — Patrol:  basic validation evidence required
  1 — Caution: + rollback note required
  2 — Action:  + failure case evidence required

Example:
  AI_IQ_RISK_TIER=1 claude   # enable Tier 1 gates for session
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Evidence patterns (regex, case-insensitive)
# ---------------------------------------------------------------------------

VALIDATION_PATTERNS: tuple[str, ...] = (
    r"\btest(s|ed|ing)?\b",
    r"\bpass(es|ed|ing)?\b",
    r"\bverif(y|ied|ication)\b",
    r"\bvalidat(e|ed|ion)\b",
    r"\bconfirm(s|ed)?\b",
    r"\bcheck(s|ed)?\b",
    r"\boutput\b",
    r"\bresult(s)?\b",
)

ROLLBACK_PATTERNS: tuple[str, ...] = (
    r"\brollback\b",
    r"\brevert\b",
    r"\bundo\b",
    r"\brestore\b",
    r"\broll\s+back\b",
)

FAILURE_PATTERNS: tuple[str, ...] = (
    r"\bfailure\b",
    r"\bfail(s|ed)?\b",
    r"\berror\s+case\b",
    r"\bnegative\s+test\b",
    r"\bedge\s+case\b",
    r"\bboundary\b",
    r"\binvalid\b",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_stdin() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _has_evidence(text: str, patterns: tuple[str, ...]) -> bool:
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in patterns)


def _gather_evidence(payload: dict[str, Any]) -> str:
    return " ".join([
        str(payload.get("task_subject", "")),
        str(payload.get("task_description", "")),
        str(payload.get("output", "")),
        str(payload.get("result", "")),
    ])


def _reject(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    payload = _read_stdin()

    # Graceful degradation: no payload → allow (non-Nelson context)
    if not payload:
        sys.exit(0)

    risk_tier = int(os.environ.get("AI_IQ_RISK_TIER", "0"))
    evidence = _gather_evidence(payload)

    # Tier 0+: require validation evidence
    if not _has_evidence(evidence, VALIDATION_PATTERNS):
        _reject(
            f"🚫 AI-IQ Quality Gate (Tier {risk_tier}): No validation evidence detected. "
            "Include test results, output, or verification before marking complete."
        )

    # Tier 1+: require rollback note
    if risk_tier >= 1 and not _has_evidence(evidence, ROLLBACK_PATTERNS):
        _reject(
            f"🚫 AI-IQ Quality Gate (Tier {risk_tier}): Rollback note required. "
            "Describe how to revert this change."
        )

    # Tier 2+: require failure case evidence
    if risk_tier >= 2 and not _has_evidence(evidence, FAILURE_PATTERNS):
        _reject(
            f"🚫 AI-IQ Quality Gate (Tier {risk_tier}): Failure case evidence required. "
            "Document edge cases or what could go wrong."
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
