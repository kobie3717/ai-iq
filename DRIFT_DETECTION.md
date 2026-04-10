# Drift Detection — Solving the Reinforced Lies Problem

## The Problem

AI memory systems face a critical flaw: **frequently accessed wrong memories become self-reinforcing**. The more a lie is cited, the stronger it becomes. Decay mechanisms kill unused bad memories but strengthen used ones — turning lies into "proven truth" through access patterns alone.

### Example Scenario

1. Memory: "Always use MongoDB for everything" (incorrect advice)
2. Gets accessed 20 times (because it's old and vague)
3. Decay system sees high access → promotes to semantic tier
4. Now it's "proven knowledge" — harder to question
5. Future queries cite it more → cycle continues
6. The lie is now immune to decay and treated as fact

## The Solution: Drift Detection & Validation

The validation module identifies high-risk memories that need human review before they become self-reinforcing.

### Risk Scoring Algorithm

Each memory gets a drift risk score (0.0-1.0) based on:

1. **Access count** (0-0.3): High access = self-reinforcement risk
   - 0 accesses = 0.0
   - 30+ accesses = 0.3

2. **Age** (0-0.25): Older = stale information risk
   - <30 days = 0.0
   - 720+ days = 0.25

3. **Citations** (0-0.2): No citations = unverified claim
   - Has citations = 0.0
   - No citations = 0.2

4. **Tier** (0-0.15): Semantic = highest trust = highest risk if wrong
   - Working = 0.0
   - Episodic = 0.05
   - Semantic = 0.15

5. **Validation** (0-0.1): Never validated = untested
   - Validated = 0.0
   - Never validated = 0.1

**Total risk score = sum of all factors (capped at 1.0)**

Example:
- Old semantic memory (200d) with 15 accesses, no citations, never validated:
  - Access: 15/30 = 0.15
  - Age: 200/720 = 0.07
  - Citations: 0.2
  - Tier: 0.15
  - Validated: 0.1
  - **Total: 0.67 (HIGH RISK)**

## CLI Commands

### Scan for Drift

```bash
memory-tool validate scan [--min-access N] [--min-age-days N]
```

Shows high-risk memories sorted by risk score. Defaults to memories with 5+ accesses and 30+ days old.

Example output:
```
⚠️  Drift Detection: High-Risk Memories Needing Validation
================================================================================
These memories are frequently accessed but may be wrong (reinforced lies).

  #42 🔴 HIGH (risk=0.89) [semantic] 15x
      Use MongoDB for everything in production
      Last validated: NEVER

  #127 🟡 MED (risk=0.62) [episodic]  8x
      Always use global variables for state
      Last validated: NEVER

Total: 2 drift candidates

Actions:
  memory-tool validate confirm <id> --notes 'verified from X'
  memory-tool validate refute <id> --notes 'this is wrong because Y'
```

### Confirm Validation

```bash
memory-tool validate confirm <id> [--notes "verified from X"] [--validator user]
```

Marks a memory as validated and correct. Records:
- Validation timestamp
- Validator (default: 'user')
- Notes (why it's correct)
- Result: 'confirmed'

### Refute Memory

```bash
memory-tool validate refute <id> [--notes "this is wrong because Y"] [--validator user]
```

Marks a memory as wrong and demotes it:
- Semantic → Episodic
- Episodic → Working
- Working → Working (can be garbage collected)

Prevents further self-reinforcement by reducing tier authority.

### List Unvalidated Semantic

```bash
memory-tool validate list-unvalidated
```

Shows all semantic tier memories that have never been validated. These are "proven knowledge" that might be reinforced lies.

### Validation Report

```bash
memory-tool validate report
```

Shows statistics:
- Validation counts by result (confirmed/refuted/uncertain)
- Validation status by tier (% validated)
- High-risk memories needing attention
- Total validations performed

## Integration with Dream Mode

Drift detection runs automatically during `memory-tool dream`:

```
⚠️  Phase: Drift Detection...
   ⚠️  3 high-risk memories need validation (potential reinforced lies)
      #42 risk=0.89 Use MongoDB for everything in production...
      #127 risk=0.62 Always use global variables for state...
      #215 risk=0.71 Never use TypeScript, always JavaScript...
   ✓ No high-risk drift detected (15 candidates scanned)
```

Dream mode output includes drift candidate count in final summary.

## Database Schema

### New Column: `memories.last_validated_at`

Timestamp of last validation (NULL if never validated).

### New Table: `validation_log`

```sql
CREATE TABLE validation_log (
    id INTEGER PRIMARY KEY,
    memory_id INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    validator TEXT NOT NULL,
    validation_type TEXT CHECK(validation_type IN ('user', 'external_source', 'llm_check', 'cross_reference')),
    result TEXT CHECK(result IN ('confirmed', 'refuted', 'uncertain')),
    notes TEXT,
    validated_at TEXT DEFAULT (datetime('now'))
);
```

Tracks all validation events:
- Who validated
- How it was validated (manual, external source, LLM check, cross-reference)
- Result (confirmed, refuted, uncertain)
- Notes explaining the decision

## Python API

```python
from memory_tool.validation import (
    find_drift_candidates,
    score_drift_risk,
    mark_validated,
    mark_refuted,
    get_unvalidated_semantic,
    validation_report
)

# Find high-risk memories
candidates = find_drift_candidates(conn, min_access_count=5, min_age_days=30)

for mem in candidates:
    risk = mem['drift_risk']
    if risk > 0.7:
        print(f"HIGH RISK: {mem['content']}")

# Score individual memory
risk = score_drift_risk({
    'access_count': 15,
    'created_at': '2024-01-01T00:00:00',
    'citations': '',
    'tier': 'semantic',
    'last_validated_at': None,
    'proof_count': 3
})

# Validate memory
mark_validated(conn, memory_id, validator='kobus', notes='verified from docs')

# Refute wrong memory
mark_refuted(conn, memory_id, validator='kobus', notes='this is anti-pattern')

# Get unvalidated semantic memories
unvalidated = get_unvalidated_semantic(conn)

# Generate report
report = validation_report(conn)
print(f"High-risk: {report['high_risk_count']}")
print(f"Semantic validated: {report['tier_stats']['semantic']['pct_validated']}%")
```

## Best Practices

### When to Validate

1. **Weekly drift scans**: Run `memory-tool validate scan` weekly
2. **After promotions**: When memories get promoted to semantic, validate them
3. **Before critical decisions**: Validate memories before using them for important choices
4. **After dream cycles**: Check drift candidates flagged by dream mode

### Validation Types

- **user**: Manual human review (default)
- **external_source**: Checked against documentation, source code, or official docs
- **llm_check**: Verified by LLM against known facts
- **cross_reference**: Confirmed by multiple independent sources

### Refutation Strategy

Don't delete refuted memories — demote them:
1. First refutation: Semantic → Episodic (reduces authority)
2. Second refutation: Episodic → Working (candidates for GC)
3. Third time: Garbage collection removes it

This creates a grace period for context and prevents abrupt loss of information.

## Testing

Comprehensive test suite in `tests/test_validation.py`:

```bash
pytest tests/test_validation.py -xvs
```

Tests cover:
- Risk scoring algorithm
- Drift candidate detection
- Validation logging
- Refutation and demotion
- Unvalidated semantic detection
- Validation reports
- Cascade delete behavior
- Multiple validation types

## Implementation Files

- **Module**: `/root/ai-memory-sqlite/memory_tool/validation.py` (200 lines)
- **Database**: `/root/ai-memory-sqlite/memory_tool/database.py` (schema updates)
- **CLI**: `/root/ai-memory-sqlite/memory_tool/cli.py` (validate command)
- **Dream**: `/root/ai-memory-sqlite/memory_tool/dream.py` (drift detection phase)
- **Tests**: `/root/ai-memory-sqlite/tests/test_validation.py` (14 tests)
- **Help**: `/root/ai-memory-sqlite/memory_tool/display.py` (help text)

## Why This Matters

This feature answers the biggest critique of reinforcement-based memory systems:

> "If you reinforce memories by access count, you'll just make your lies stronger."

Drift detection breaks the self-reinforcing cycle by:
1. Identifying high-access memories BEFORE they become immune
2. Requiring human validation for "proven knowledge"
3. Demoting refuted memories to prevent further reinforcement
4. Making validation status explicit and trackable

**Ship ugly, fix Tuesday.** The algorithm is simple, explicit, and documented. Future improvements can refine the risk factors, but the core mechanism is sound.
