"""Output formatting and help display."""

import sqlite3
import sys
import os
import re
import json
import shutil
import subprocess
import hashlib
import math
from datetime import datetime, timedelta
from pathlib import Path
from difflib import SequenceMatcher
from typing import Optional, List, Dict, Tuple, Any, Union

# Import from our modular components
from .config import *
from .database import get_db, has_vec_support
from .utils import auto_tag, word_set, normalize, find_similar, word_overlap, similarity
from .fsrs import fsrs_retention, fsrs_new_stability, fsrs_new_difficulty, fsrs_next_interval, fsrs_auto_rating
from .importance import update_importance
from .embedding import embed_and_store, embed_text, semantic_search

# Lazy imports for optional dependencies
try:
    import numpy as np
    import sqlite_vec
except ImportError:
    pass


# Lazy imports to avoid circular dependency
def _get_memory_functions() -> Tuple[Any, Any]:
    """Lazy import of memory functions to avoid circular dependency."""
    from .memory_ops import get_memory
    from .relations import get_related
    return get_memory, get_related


def format_row(row: sqlite3.Row) -> str:
    """Full verbose format."""
    tags = f" tags:{row['tags']}" if row["tags"] else ""
    proj = f" project:{row['project']}" if row["project"] else ""
    stale = " [STALE]" if row["stale"] else ""
    acc = f" acc:{row['access_count']}" if row["access_count"] else ""
    exp = ""
    if row["expires_at"]:
        if row["expires_at"] < datetime.now().isoformat():
            exp = " [EXPIRED]"
        else:
            exp = f" [expires:{row['expires_at'][:10]}]"
    src = f" src:{row['source']}" if row["source"] != "manual" else ""
    key = ""
    rev = ""
    try:
        if row["topic_key"]:
            key = f" key:{row['topic_key']}"
    except (KeyError, IndexError):
        pass
    try:
        if row["revision_count"] and row["revision_count"] > 1:
            rev = f" rev:{row['revision_count']}"
    except (KeyError, IndexError):
        pass
    derived = ""
    try:
        if row["derived_from"]:
            derived = f" derived:{row['derived_from']}"
    except (KeyError, IndexError, TypeError):
        pass
    return (f"  #{row['id']} [{row['category']}]{proj}{tags}{acc}{stale}{exp}{src}{key}{rev}{derived}"
            f" ({row['updated_at'][:10]})\n    {row['content']}")




def format_row_compact(row: sqlite3.Row, show_tokens: bool = True) -> str:
    """Compact format (v4 Feature #1 + claude-mem progressive disclosure).

    Args:
        row: Memory row from database
        show_tokens: If True, append estimated token cost (default: True)
    """
    content_preview = row['content'][:80]
    if len(row['content']) > 80:
        content_preview += "..."
    proj = f" project:{row['project']}" if row["project"] else ""
    acc = f" ({row['access_count']}x)" if row["access_count"] else ""
    imp = ""
    try:
        if row['imp_score']:
            imp = f" ⚡{row['imp_score']:.1f}"
    except (KeyError, IndexError, TypeError):
        pass

    # Proof count indicator (Hindsight Feature #3)
    proof = ""
    try:
        if 'proof_count' in row.keys() and row['proof_count'] and row['proof_count'] > 1:
            proof = f" (backed by {row['proof_count']} sources)"
    except (KeyError, IndexError, TypeError):
        pass

    # Token estimate (claude-mem style) - always show for progressive disclosure
    tokens = estimate_tokens(row['content'])
    token_str = f" ~{tokens}tok"

    return f"[{row['id']}] {row['category']} | {content_preview}{acc}{imp}{proof} {token_str}"




def print_memory_full(mem_id: int) -> None:
    """Print full detail for a single memory (v4 Feature #1)."""
    get_memory_func, get_related_func = _get_memory_functions()
    mem = get_memory_func(mem_id)
    if not mem:
        print(f"Memory #{mem_id} not found.")
        return

    print(f"\n=== Memory #{mem['id']} ===")
    print(f"Category: {mem['category']}")
    print(f"Content: {mem['content']}")
    if mem["project"]:
        print(f"Project: {mem['project']}")
    if mem["tags"]:
        print(f"Tags: {mem['tags']}")
    print(f"Priority: {mem['priority']}")
    print(f"Created: {mem['created_at']}")
    print(f"Updated: {mem['updated_at']}")
    if mem["accessed_at"]:
        print(f"Last accessed: {mem['accessed_at']}")
    print(f"Access count: {mem['access_count']}")

    # FSRS retention info
    try:
        if mem["fsrs_stability"]:
            stability = mem["fsrs_stability"]
            difficulty = mem["fsrs_difficulty"] if mem["fsrs_difficulty"] else 5.0
            last_acc = mem["last_accessed_at"] if mem["last_accessed_at"] else mem["updated_at"]
            try:
                last_dt = datetime.fromisoformat(last_acc.replace('Z', '+00:00')).replace(tzinfo=None)
                elapsed = (datetime.now() - last_dt).total_seconds() / 86400
                retention = fsrs_retention(stability, elapsed)
                next_int = fsrs_next_interval(stability)
                ret_pct = f"{retention*100:.0f}%"
                bar = "█" * int(retention * 10) + "░" * (10 - int(retention * 10))
                print(f"Retention: {bar} {ret_pct} (S:{stability:.1f} D:{difficulty:.1f} next:{next_int:.0f}d)")
            except Exception as e:
                pass
    except (KeyError, TypeError):
        pass

    # Importance score
    try:
        if mem["imp_score"]:
            print(f"Importance: {mem['imp_score']:.1f}/10 (N:{mem['imp_novelty']:.0f} R:{mem['imp_relevance']:.0f} F:{mem['imp_frequency']:.0f} I:{mem['imp_impact']:.0f})")
    except (KeyError, IndexError, TypeError):
        pass

    if mem["stale"]:
        print(f"Status: STALE")
    if mem["expires_at"]:
        print(f"Expires: {mem['expires_at']}")
    print(f"Source: {mem['source']}")
    try:
        if mem["topic_key"]:
            print(f"Topic key: {mem['topic_key']}")
    except (KeyError, IndexError):
        pass
    try:
        if mem["revision_count"] and mem["revision_count"] > 1:
            print(f"Revisions: {mem['revision_count']}")
    except (KeyError, IndexError):
        pass

    # Provenance fields
    try:
        if mem["derived_from"]:
            print(f"Derived from: {mem['derived_from']}")
    except (KeyError, IndexError, TypeError):
        pass
    try:
        if mem["citations"]:
            print(f"Citations: {mem['citations']}")
    except (KeyError, IndexError, TypeError):
        pass
    try:
        if mem["reasoning"]:
            print(f"Reasoning: {mem['reasoning']}")
    except (KeyError, IndexError, TypeError):
        pass

    # Proof tracking (Hindsight Feature #3)
    try:
        if 'proof_count' in mem.keys() and mem["proof_count"] and mem["proof_count"] > 1:
            print(f"Proof: Confirmed by {mem['proof_count']} sources")
            if mem["source_memory_ids"]:
                sources = json.loads(mem["source_memory_ids"])
                source_ids_str = ", ".join(f"#{s}" for s in sources)
                print(f"  Source IDs: {source_ids_str}")
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        pass

    # Related memories
    related = get_related_func(mem_id)
    if related:
        print("\nRelated memories:")
        for r in related:
            print(f"  -> #{r['id']} ({r['relation_type']}): {r['content']}")
    print()




def estimate_tokens(text: str) -> int:
    """Estimate token count using word count * 1.3 heuristic (claude-mem approach).

    This is more accurate than chars/4 for natural language. Technical text
    tends to have more tokens per word, so 1.3x is a reasonable conservative estimate.
    """
    if not text:
        return 0
    word_count = len(text.split())
    return max(1, int(word_count * 1.3))


def show_token_economics(rows: List[sqlite3.Row], compact: bool = True) -> None:
    """Display token budget summary (claude-mem progressive disclosure).

    Shows total estimated tokens and suggests using 'get <id>' for full detail.
    """
    if not rows:
        return

    # Calculate total tokens for all results
    total_tokens = sum(estimate_tokens(r['content']) for r in rows)

    # In compact mode, show preview token estimate
    if compact:
        # Estimate tokens shown in preview (80 chars preview + metadata ~30 chars)
        preview_tokens = sum(estimate_tokens(r['content'][:80]) + 8 for r in rows)
        avg_tokens = total_tokens // max(1, len(rows))
        print(f"\n{len(rows)} results (~{total_tokens} tokens total). Use --full for details or `memory-tool get <id>` for single memory.")
    else:
        # Full mode: show total tokens
        print(f"\n💰 Full context loaded: ~{total_tokens} tokens")


def print_help() -> None:
    """Print comprehensive help documentation."""
    help_text = """
Claude Code Persistent Memory System v5 + FSRS-6 Spaced Repetition
SQLite-backed with FTS, dedup, relationships, FSRS decay, smart context, auto-snapshots,
auto-tagging, expiry, error capture hook, backup/restore, progressive disclosure,
topic-key upserts, conflict detection, smart ingest, topic file export.
Phase 2: Hybrid search with semantic embeddings (sqlite-vec) + RRF fusion.
Phase 3: Graph intelligence with entities, relationships, facts, and spreading activation.
Phase 6: FSRS-6 spaced repetition model for intelligent memory decay and retention tracking.

Usage:
  memory-tool add <category> <content> [--tags t1,t2] [--project X] [--priority N] [--related ID] [--expires YYYY-MM-DD] [--key topic-key] [--derived-from ID1,ID2] [--citations "URL1;path2"] [--reasoning "why"]
  memory-tool search <query> [--full] [--semantic] [--keyword] [--budget N]  # Hybrid search (default), --semantic for semantic-only, --keyword for FTS-only, --budget to limit tokens
  memory-tool get <id>                          # Show full detail for single memory
  memory-tool list [--category X] [--project X] [--tag X] [--stale] [--expired]
  memory-tool update <id> <content>
  memory-tool delete <id>
  memory-tool tag <id> <tags>
  memory-tool relate <id1> <id2> [type]         # Link related memories
  memory-tool conflicts                         # Find potential duplicate memories
  memory-tool merge <id1> <id2>                 # Merge two similar memories
  memory-tool supersede <old_id> <new_id>       # Mark old memory as superseded by new
  memory-tool pending                           # Show pending/todo items
  memory-tool projects                          # Project summary
  memory-tool topics                            # Generate topic .md files per project
  memory-tool export [--project X]              # Regenerate MEMORY.md (smart context)
  memory-tool stats                             # Full statistics (includes vector index & graph)
  memory-tool next                              # Suggest next actions based on current memory state
  memory-tool dream                             # Review transcripts, consolidate memories, normalize dates (AI memory REM sleep)
  memory-tool capture-correction "<text>"       # Extract and store corrections from user feedback
  memory-tool correct "<text>"                  # Queue a correction manually
  memory-tool corrections                       # Show pending corrections
  memory-tool apply-correction <id>             # Apply correction as memory
  memory-tool dismiss-correction <id>           # Dismiss a correction
  memory-tool detect "<text>"                   # Detect correction in text
  memory-tool stale                             # Review stale memories
  memory-tool decay                             # Flag stale, deprioritize, expire (FSRS-6)
  memory-tool consolidate                       # Cross-memory consolidation (merge, patterns, prune)
  memory-tool retention                         # Show memories by retention (lowest first)
  memory-tool importance                        # Show memories ranked by importance score
  memory-tool reindex                           # Bulk-embed all active memories for vector search
  memory-tool snapshot <summary> [--project X]  # Save session snapshot
  memory-tool auto-snapshot                     # Auto-generate snapshot from git/file changes
  memory-tool snapshots [--limit N]             # View recent snapshots
  memory-tool detect-project                    # Auto-detect project from cwd
  memory-tool gc [days]                         # Garbage collect old inactive memories
  memory-tool log-error <command> <error>       # Log a failed command as error memory
  memory-tool import-md <file>                  # Import memories from session summary markdown
  memory-tool backup                            # Backup database
  memory-tool restore <file>                    # Restore database from backup
  memory-tool session-log [--limit N] [--errors]  # Show current session tool executions (default: last 50)

Mode Profiles:
  memory-tool mode                              # Show current mode
  memory-tool mode list                         # List all available modes
  memory-tool mode <name>                       # Switch to mode (default/dev/ops/research/monitor)

Graph Intelligence (Phase 3):
  memory-tool graph                             # Show graph summary
  memory-tool graph add <type> <name> [summary] # Add entity (types: person/project/org/feature/concept/tool/service)
  memory-tool graph rel <from> <rel_type> <to> [note]  # Add relationship (types: knows/works_on/owns/depends_on/built_by/uses/blocks/related_to)
  memory-tool graph fact <entity> <key> <value> # Set fact on entity
  memory-tool graph get <name>                  # Show entity with facts & relationships
  memory-tool graph list [type]                 # List entities
  memory-tool graph delete <name>               # Delete entity
  memory-tool graph spread <name> [depth]       # Spreading activation (default depth=2)
  memory-tool graph link <memory_id> <entity>   # Link memory to entity
  memory-tool graph auto-link                   # Auto-link all memories to entities
  memory-tool graph import-openclaw             # Import from OpenClaw graph DB
  memory-tool graph stats                       # Graph statistics

OpenClaw Bridge (Phase 4):
  memory-tool sync                              # Bidirectional sync (to + from OpenClaw)
  memory-tool sync-to                           # Export only (Claude Code → OpenClaw)
  memory-tool sync-from                         # Import only (OpenClaw → Claude Code)

Run Tracking (Phase 5):
  memory-tool run start "task description" [--agent claw|claude] [--project X] [--tags x,y]
  memory-tool run step <id> "step description"
  memory-tool run complete <id> "outcome summary"
  memory-tool run fail <id> "reason"
  memory-tool run list [--status running|completed|failed] [--project X] [--limit 10]
  memory-tool run show <id>                     # Show full run detail including all steps
  memory-tool run cancel <id>

Search Feedback & Learning (Phase 6):
  memory-tool feedback <search_id> <id1,id2,id3>  # Log which search results were used
  memory-tool feedback good|bad|meh ["reason"]  # Record user feedback on last AI action
  memory-tool feedback                          # Show recent feedback entries
  memory-tool feedback --stats                  # Show feedback statistics (good/bad/meh counts)
  memory-tool feedback-stats                    # Show search quality metrics and helpful/unhelpful memories
  memory-tool gaps                              # Show knowledge gaps (queries with poor results)
  memory-tool search-quality                    # Alias for feedback-stats
  memory-tool hot                               # Show most frequently accessed memories (immune to decay)

Beliefs & Predictions (Phase 7):
  memory-tool believe "<statement>" [--confidence 0.8] [--based-on <id>] [--project X]
                                                # Create belief with explicit confidence
  memory-tool predict "<prediction>" [--based-on <id>] [--confidence 0.6] [--deadline YYYY-MM-DD] [--expect "<outcome>"]
                                                # Create prediction based on belief
  memory-tool resolve <prediction_id> --confirmed|--refuted [--outcome "<what happened>"]
                                                # Resolve prediction (triggers Bayesian propagation)
  memory-tool beliefs [--weak|--strong|--conflicts]
                                                # List beliefs sorted by confidence
  memory-tool predictions [--open|--confirmed|--refuted|--expired]
                                                # List predictions by status

Extended Beliefs System (explicit beliefs with evidence tracking):
  memory-tool believe "<statement>" [--confidence 0.5] [--category general] [--source user] [--memory <id>]
                                                # Create explicit belief (separate from memories)
  memory-tool evidence <belief_id> <memory_id> --supports|--contradicts [--strength 0.5] [--note "text"]
                                                # Add evidence for/against a belief (triggers Bayesian update)
  memory-tool belief-stats                      # Show belief accuracy, calibration, strongest/weakest beliefs
  memory-tool expired-predictions               # List predictions past deadline that need resolution

Categories: project, decision, preference, error, learning, pending, architecture, workflow, contact, belief
Priority: 0 (low) to 10 (high). Auto-adjusts based on access frequency.
Vector search: Requires sqlite-vec, onnxruntime, tokenizers, numpy. Model: all-MiniLM-L6-v2 (384-dim).
"""
    print(help_text.strip())


# ── Run Tracking System ──


