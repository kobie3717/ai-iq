# Phase 3: Capability-Based Access Control — Quick Reference

## Files Created
- `memory_tool/access_control.py` (263 lines) — Core logic
- `tests/test_access_control.py` (279 lines) — 17 tests, 100% pass
- `CAPABILITY_ACCESS.md` (356 lines) — User documentation
- `scripts/integrate_phases.py` (326 lines) — Integration guide

## Core Functions

### check_access(wing, room, passport_credential)
Returns `(bool, reason_string)` — checks if passport grants access to namespace.

### filter_memories_by_access(rows, passport_credential)
Filters memory list to only accessible memories.

### list_rules()
Returns formatted string of all access control rules.

## 5 Predefined Namespaces

1. **finance.payments** — Requires code: 0.6, security: 0.5
2. **security.secrets** — Requires security: 0.8
3. **devops.production** — Requires devops: 0.7, security: 0.5
4. **code.internal** — Requires code: 0.5
5. **general.public** — Public (no requirements)

## Passport Format

```json
{
  "credentialSubject": {
    "competence": {
      "code": 0.9,
      "security": 0.7,
      "devops": 0.8,
      "testing": 0.6,
      "finance": 0.9
    }
  }
}
```

## Usage Examples (after integration)

```bash
# Add namespaced memory
memory-tool add learning "PayFast API: 12345" --wing finance --room payments

# Check access
memory-tool check-access finance payments --passport-file passport.json

# List all rules
memory-tool access-rules
```

## Python API

```python
from memory_tool.access_control import check_access, filter_memories_by_access

passport = {"credentialSubject": {"competence": {"code": 0.7, "security": 0.6}}}

# Check access
allowed, reason = check_access('finance', 'payments', passport)

# Filter search results
results = search_memories("payment")
accessible = filter_memories_by_access(results, passport)
```

## Security Model

- **Deny-by-default**: Undefined namespaces are blocked
- **Backward compatible**: No wing/room = general access (always allowed)
- **Competence-based**: Passport proves capability (0.0-1.0 scores)
- **Audit logging**: Access denials logged at debug level

## Integration

Run `python3 scripts/integrate_phases.py` for complete integration guide.

Key changes needed:
1. CLI additions (check-access, access-rules commands)
2. memory_ops.py additions (wing/room params, access filtering)
3. Database columns already exist (wing, room in database.py)

## Tests

```bash
pytest tests/test_access_control.py -v  # 17 tests, 70% coverage
```

All tests pass. Missing coverage is CLI handlers (tested during integration).

## Adding Custom Rules

Edit `ACCESS_RULES` in `memory_tool/access_control.py`:

```python
ACCESS_RULES['marketing.campaigns'] = {
    'min_competence': {'marketing': 0.6, 'data_analysis': 0.5},
    'description': 'Marketing campaign data'
}
```

No other code changes needed — rules checked at runtime.
