#!/usr/bin/env python3
"""
Integration script for Phases 1, 2, and 3.

This script provides copy-paste ready code blocks to integrate all three parallel phases:
- Phase 1: Memory Tiers (working/episodic/semantic)
- Phase 2: Passport Credentials (DID-based identity)
- Phase 3: Capability-Based Access Control (wing/room namespaces)

Since the three phases were developed in parallel to avoid merge conflicts,
this script outputs the exact code that needs to be added to shared files.

Usage:
    python scripts/integrate_phases.py

Output:
    1. CLI command additions for cli.py
    2. Memory operation additions for memory_ops.py
    3. Import statements needed
    4. Database migration checks

DO NOT run this script directly on the files. Instead, review the output
and manually apply the changes to ensure correctness.
"""

import sys


def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_code_block(description, code):
    """Print a labeled code block."""
    print(f"### {description}\n")
    print("```python")
    print(code.strip())
    print("```\n")


def phase1_cli_additions():
    """CLI additions for Phase 1: Memory Tiers."""
    return """
# Add to cli.py imports section
from memory_tool.tiers import (
    tier_stats,
    promote_tier_pass,
    demote_tier_pass,
    expire_working,
    promote_memory_to_tier,
    demote_memory_to_tier
)

# Add to main() function's subparser section
tier_parser = subparsers.add_parser('tier-stats', help='Show memory tier statistics')

promote_parser = subparsers.add_parser('tier-promote', help='Promote memory to higher tier')
promote_parser.add_argument('memory_id', type=int, help='Memory ID to promote')
promote_parser.add_argument('--tier', required=True, choices=['episodic', 'semantic'], help='Target tier')

demote_parser = subparsers.add_parser('tier-demote', help='Demote memory to lower tier')
demote_parser.add_argument('memory_id', type=int, help='Memory ID to demote')
demote_parser.add_argument('--tier', required=True, choices=['working', 'episodic'], help='Target tier')

tier_pass_parser = subparsers.add_parser('tier-pass', help='Run automatic tier promotion/demotion')
tier_pass_parser.add_argument('--promote', action='store_true', help='Promote episodic to semantic')
tier_pass_parser.add_argument('--demote', action='store_true', help='Demote unused semantic to episodic')
tier_pass_parser.add_argument('--expire', action='store_true', help='Expire old working memories')

# Add to command routing section
elif args.command == 'tier-stats':
    tier_stats()
elif args.command == 'tier-promote':
    if promote_memory_to_tier(args.memory_id, args.tier):
        print(f"✓ Memory #{args.memory_id} promoted to {args.tier}")
    else:
        print(f"✗ Failed to promote memory #{args.memory_id}")
elif args.command == 'tier-demote':
    if demote_memory_to_tier(args.memory_id, args.tier):
        print(f"✓ Memory #{args.memory_id} demoted to {args.tier}")
    else:
        print(f"✗ Failed to demote memory #{args.memory_id}")
elif args.command == 'tier-pass':
    if args.promote:
        count = promote_tier_pass()
        print(f"✓ Promoted {count} memories to semantic tier")
    if args.demote:
        count = demote_tier_pass()
        print(f"✓ Demoted {count} memories to episodic tier")
    if args.expire:
        count = expire_working()
        print(f"✓ Expired {count} working memories")
"""


def phase2_cli_additions():
    """CLI additions for Phase 2: Passport Credentials."""
    return """
# Add to cli.py imports section
from memory_tool.passport import get_passport, display_passport

# Add to main() function's subparser section
passport_parser = subparsers.add_parser('passport', help='Get complete memory passport')
passport_parser.add_argument('memory_id', type=int, help='Memory ID')

# Add to command routing section
elif args.command == 'passport':
    passport = get_passport(args.memory_id)
    if passport:
        display_passport(passport)
    else:
        print(f"Memory #{args.memory_id} not found or inactive")
"""


def phase3_cli_additions():
    """CLI additions for Phase 3: Access Control."""
    return """
# Add to cli.py imports section
from memory_tool.access_control import cmd_check_access, cmd_access_rules

# Add to main() function's subparser section
check_access_parser = subparsers.add_parser('check-access', help='Check access to a namespace')
check_access_parser.add_argument('wing', help='Namespace wing (e.g., finance)')
check_access_parser.add_argument('room', help='Namespace room (e.g., payments)')
check_access_parser.add_argument('--passport-file', help='Path to passport JSON file')

access_rules_parser = subparsers.add_parser('access-rules', help='List all access control rules')

# Add to command routing section
elif args.command == 'check-access':
    cmd_check_access(args)
elif args.command == 'access-rules':
    cmd_access_rules(args)
"""


def phase1_memory_ops_additions():
    """memory_ops.py additions for Phase 1."""
    return """
# Add to add_memory() function, after memory insertion:
from memory_tool.tiers import classify_tier

# Inside add_memory(), after INSERT but before commit:
# Auto-classify tier on new memories
tier = classify_tier({
    'category': category,
    'priority': priority,
    'tags': tags or '',
    'proof_count': proof_count,
    'expires_at': expires,
    'access_count': 0
})
conn.execute("UPDATE memories SET tier = ? WHERE id = ?", (tier, memory_id))
"""


def phase3_memory_ops_additions():
    """memory_ops.py additions for Phase 3."""
    return """
# Add to add_memory() function signature:
def add_memory(
    content: str,
    category: str = "learning",
    project: Optional[str] = None,
    tags: Optional[str] = None,
    priority: int = 0,
    topic_key: Optional[str] = None,
    derived_from: Optional[List[int]] = None,
    citations: Optional[List[str]] = None,
    reasoning: Optional[str] = None,
    expires: Optional[str] = None,
    source: str = "manual",
    wing: Optional[str] = None,  # NEW
    room: Optional[str] = None   # NEW
) -> int:

# Add to INSERT statement parameters (after expires):
INSERT INTO memories (
    category, content, project, tags, priority, topic_key,
    derived_from, citations, reasoning, expires_at, source,
    wing, room  # NEW
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

# Add wing and room to the tuple:
(category, content, project, tags, priority, topic_key,
 derived_from_json, citations_json, reasoning, expires, source,
 wing, room)

# Add to search_memories() function:
from memory_tool.access_control import filter_memories_by_access

def search_memories(
    query: str,
    semantic: bool = False,
    keyword_only: bool = False,
    project: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[str] = None,
    passport: Optional[Dict[str, Any]] = None  # NEW
) -> List[Dict[str, Any]]:
    # ... existing search logic ...

    # Before returning results, filter by access control:
    if passport:
        results = filter_memories_by_access(results, passport)

    return results
"""


def database_migration_check():
    """Check if database already has needed columns."""
    return """
# The database.py file should already have these columns added in init_db().
# Phase 1 needs: tier (already added)
# Phase 3 needs: wing, room (already added)
# Phase 2 uses existing passport.py (no DB changes needed)

# Verify with:
# sqlite3 ~/.ai-iq/memories.db ".schema memories"

# Expected columns:
# - tier TEXT DEFAULT 'episodic' CHECK(tier IN ('working', 'episodic', 'semantic'))
# - wing TEXT DEFAULT NULL
# - room TEXT DEFAULT NULL
"""


def main():
    """Output integration instructions."""
    print("=" * 80)
    print("  AI-IQ Phase 1-3 Integration Guide")
    print("  Generated:", "2026-04-09")
    print("=" * 80)
    print("\nThis script outputs the exact code additions needed to integrate")
    print("all three parallel development phases into the shared files.\n")
    print("IMPORTANT: Review each block and manually apply to the target files.")
    print("DO NOT copy-paste blindly — understand the changes first.\n")

    # Phase 1: Memory Tiers
    print_section("PHASE 1: Memory Tiers — CLI Additions")
    print_code_block(
        "Add to /root/ai-memory-sqlite/memory_tool/cli.py",
        phase1_cli_additions()
    )

    print_code_block(
        "Add to /root/ai-memory-sqlite/memory_tool/memory_ops.py",
        phase1_memory_ops_additions()
    )

    # Phase 2: Passport Credentials
    print_section("PHASE 2: Passport Credentials — CLI Additions")
    print_code_block(
        "Add to /root/ai-memory-sqlite/memory_tool/cli.py",
        phase2_cli_additions()
    )
    print("NOTE: Phase 2 passport.py is standalone, no memory_ops changes needed.\n")

    # Phase 3: Access Control
    print_section("PHASE 3: Access Control — CLI Additions")
    print_code_block(
        "Add to /root/ai-memory-sqlite/memory_tool/cli.py",
        phase3_cli_additions()
    )

    print_code_block(
        "Add to /root/ai-memory-sqlite/memory_tool/memory_ops.py",
        phase3_memory_ops_additions()
    )

    # Database migration check
    print_section("DATABASE MIGRATION CHECK")
    print(database_migration_check())

    # Testing
    print_section("TESTING")
    print("""
After integration, run the test suites to verify:

    pytest tests/test_tiers.py -v           # Phase 1
    pytest tests/test_passport.py -v        # Phase 2 (if exists)
    pytest tests/test_access_control.py -v  # Phase 3

    # Full test suite
    pytest tests/ -v
""")

    # Final notes
    print_section("FINAL NOTES")
    print("""
1. All three phases were developed in parallel to avoid blocking dependencies.
2. The shared files (cli.py, memory_ops.py, database.py) were NOT modified by phases.
3. Each phase created only NEW files:
   - Phase 1: memory_tool/tiers.py, tests/test_tiers.py, migrate_tiers.py
   - Phase 2: memory_tool/passport.py (standalone, already committed)
   - Phase 3: memory_tool/access_control.py, tests/test_access_control.py, CAPABILITY_ACCESS.md

4. Database migrations:
   - Phase 1: tier column (run migrate_tiers.py)
   - Phase 3: wing, room columns (already in database.py init_db())

5. Integration order:
   a. Review and apply CLI additions from all 3 phases
   b. Review and apply memory_ops additions (Phase 1 + Phase 3)
   c. Run database migration (migrate_tiers.py)
   d. Run full test suite
   e. Update documentation (README.md, CHANGELOG.md)

6. Conflict resolution:
   - If you find conflicts in cli.py command routing, ensure each phase's
     commands are in the correct elif block
   - memory_ops.py changes from Phase 1 and 3 are in different functions
     (add_memory signature vs. tier classification)

Good luck with the integration!
""")


if __name__ == "__main__":
    main()
