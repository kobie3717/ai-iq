# Capability-Based Access Control

AI-IQ implements capability-based access control for memory namespaces using a deny-by-default security model. Memories can be organized into namespaced wings and rooms, with access controlled by passport credentials that prove competence.

## Overview

**Wing.Room Namespaces**: Organize memories into hierarchical namespaces (e.g., `finance.payments`, `security.secrets`).

**Passport Credentials**: JSON documents containing competence scores across domains (code, security, devops, etc.).

**Deny-by-Default**: Any namespace not explicitly defined in access rules is automatically blocked.

## Predefined Access Rules

AI-IQ includes 5 predefined namespaces with different access requirements:

### 1. finance.payments
**Description**: Payment processing code and configs  
**Required Competence**:
- code: 0.6
- security: 0.5

**Use Case**: Store payment API keys, transaction logic, PayFast/Stripe configs.

### 2. security.secrets
**Description**: Credentials and keys  
**Required Competence**:
- security: 0.8

**Use Case**: Database passwords, API tokens, encryption keys. Highest security threshold.

### 3. devops.production
**Description**: Production deployment configs  
**Required Competence**:
- devops: 0.7
- security: 0.5

**Use Case**: Production server configs, deployment scripts, infrastructure as code.

### 4. code.internal
**Description**: Internal codebase access  
**Required Competence**:
- code: 0.5

**Use Case**: Private implementation details, internal APIs, architecture decisions.

### 5. general.public
**Description**: Publicly accessible knowledge  
**Required Competence**: None (public)

**Use Case**: Documentation, public tutorials, open-source references.

## How to Use

### Assigning Wing/Room to Memories

When adding a memory, specify the namespace using `--wing` and `--room`:

```bash
# Store payment config in finance.payments namespace
memory-tool add learning "PayFast merchant ID: 12345" \
  --wing finance --room payments \
  --project FlashVault

# Store database password in security.secrets namespace
memory-tool add learning "Postgres password: super_secret_123" \
  --wing security --room secrets

# Store production nginx config in devops.production namespace
memory-tool add architecture "Production nginx uses rate limiting" \
  --wing devops --room production \
  --project FlashVault

# Store internal API design in code.internal namespace
memory-tool add decision "Use GraphQL for internal service mesh" \
  --wing code --room internal

# Store public knowledge (no restrictions)
memory-tool add learning "React Hooks introduced in v16.8" \
  --wing general --room public
```

### Memories Without Namespace

Memories without `--wing` and `--room` are treated as **general access** and are always accessible (backward compatible with existing memories).

```bash
# General access memory (no restrictions)
memory-tool add learning "Always use prepared statements for SQL"
```

### Passport Credentials

A passport credential is a JSON document containing competence scores:

```json
{
  "credentialSubject": {
    "competence": {
      "code": 0.9,
      "security": 0.7,
      "devops": 0.8,
      "testing": 0.6,
      "documentation": 0.5
    }
  }
}
```

**Competence Scores**: Range from 0.0 to 1.0, where:
- 0.0-0.3: Novice
- 0.3-0.5: Intermediate
- 0.5-0.7: Advanced
- 0.7-0.9: Expert
- 0.9-1.0: Master

### Checking Access

Check if a passport grants access to a namespace:

```bash
# Create passport file
cat > finance_bot_passport.json <<EOF
{
  "credentialSubject": {
    "competence": {
      "code": 0.7,
      "security": 0.6,
      "finance": 0.9
    }
  }
}
EOF

# Check access to finance.payments
memory-tool check-access finance payments --passport-file finance_bot_passport.json
# Output: ✓ ACCESS GRANTED to 'finance.payments'
#         Reason: Competence requirements met for 'finance.payments'

# Check access to security.secrets
memory-tool check-access security secrets --passport-file finance_bot_passport.json
# Output: ✗ ACCESS DENIED to 'security.secrets'
#         Reason: Insufficient competence for 'security.secrets': security: 0.60 < 0.80
```

### Viewing Access Rules

List all access control rules:

```bash
memory-tool access-rules
```

Output:
```
Access Control Rules:
======================================================================

code.internal
  Description: Internal codebase access
  Required Competence:
    - code: 0.50

devops.production
  Description: Production deployment configs
  Required Competence:
    - devops: 0.70
    - security: 0.50

finance.payments
  Description: Payment processing code and configs
  Required Competence:
    - code: 0.60
    - security: 0.50

general.public
  Description: Publicly accessible knowledge
  Access: PUBLIC (no competence required)

security.secrets
  Description: Credentials and keys
  Required Competence:
    - security: 0.80

======================================================================
Deny-by-default: All undefined namespaces are blocked.
```

## Access Control Logic

AI-IQ follows this decision flow when checking memory access:

1. **No Wing/Room**: If memory has no wing or room → **ALLOW** (general access)
2. **Namespace Lookup**: If `wing.room` not in ACCESS_RULES → **DENY** (deny-by-default)
3. **Public Check**: If rule has empty `min_competence` → **ALLOW** (public namespace)
4. **Passport Required**: If no passport provided → **DENY** (authentication required)
5. **Competence Check**: For each required domain:
   - If passport competence ≥ threshold → continue
   - If passport competence < threshold → **DENY** (insufficient competence)
6. **All Passed**: If all domain thresholds met → **ALLOW**

## Example Use Cases

### Finance Bot
A specialized bot for payment processing:

```json
{
  "credentialSubject": {
    "competence": {
      "code": 0.7,
      "security": 0.6,
      "finance": 0.9
    }
  }
}
```

**Can Access**:
- `finance.payments` (code: 0.7 ≥ 0.6, security: 0.6 ≥ 0.5)
- `code.internal` (code: 0.7 ≥ 0.5)
- `general.public` (public)
- General access memories (no namespace)

**Cannot Access**:
- `security.secrets` (security: 0.6 < 0.8)
- `devops.production` (security: 0.6 ≥ 0.5, but devops: 0.0 < 0.7)

### DevOps Bot
A bot specialized in infrastructure and deployments:

```json
{
  "credentialSubject": {
    "competence": {
      "devops": 0.9,
      "security": 0.7,
      "code": 0.4
    }
  }
}
```

**Can Access**:
- `devops.production` (devops: 0.9 ≥ 0.7, security: 0.7 ≥ 0.5)
- `general.public` (public)
- General access memories

**Cannot Access**:
- `security.secrets` (security: 0.7 < 0.8)
- `finance.payments` (code: 0.4 < 0.6)
- `code.internal` (code: 0.4 < 0.5)

## Adding Custom Rules

To add custom access rules, edit `memory_tool/access_control.py`:

```python
ACCESS_RULES = {
    # Existing rules...
    
    # Add your custom namespace
    'marketing.campaigns': {
        'min_competence': {'marketing': 0.6, 'data_analysis': 0.5},
        'description': 'Marketing campaign data and analytics'
    },
    'legal.contracts': {
        'min_competence': {'legal': 0.8},
        'description': 'Legal documents and contracts'
    },
}
```

**Important**: After modifying ACCESS_RULES, no code changes are needed. The rules are checked at runtime.

## Security Model

### Deny-by-Default
Any namespace not explicitly defined in ACCESS_RULES is **automatically blocked**, even with high competence. This prevents accidental access to undefined namespaces.

Example:
```bash
# Even with max competence, undefined namespace is blocked
memory-tool check-access unknown namespace --passport-file max_passport.json
# Output: ✗ ACCESS DENIED to 'unknown.namespace'
#         Reason: Undefined namespace 'unknown.namespace' (deny-by-default)
```

### Defense in Depth
1. **Namespace isolation**: Memories are segregated by wing.room
2. **Competence proof**: Passport credentials prove capability
3. **Deny-by-default**: Unknown namespaces are blocked
4. **Audit logging**: Access denials are logged (debug level)

## Integration with Search

When searching memories with a passport, only accessible memories are returned:

```python
from memory_tool.memory_ops import search_memories
from memory_tool.access_control import filter_memories_by_access

# Search all memories
results = search_memories("payment processing")

# Filter by passport
passport = {
    "credentialSubject": {
        "competence": {"code": 0.7, "security": 0.6}
    }
}
accessible_results = filter_memories_by_access(results, passport)
```

**Result**: Only memories that the passport can access are returned. Security-sensitive memories are invisible to unauthorized passports.

## Future Extensions

Planned enhancements:

- **Time-based access**: Grant temporary access that expires
- **Role-based templates**: Predefined competence profiles (e.g., "junior_dev", "security_auditor")
- **Delegation chains**: Passport A can delegate subset of competence to Passport B
- **Audit trails**: Detailed logs of all access attempts (granted and denied)
- **Dynamic rules**: Load ACCESS_RULES from external config file or database

## Best Practices

1. **Use namespaces for sensitive data**: Payment configs, credentials, production secrets
2. **Keep general access for documentation**: Public knowledge, tutorials, open-source refs
3. **Match competence to risk**: Higher security requirements for secrets
4. **Regular audits**: Review access logs to detect anomalies
5. **Principle of least privilege**: Grant minimum competence needed for task
6. **Document custom rules**: Add clear descriptions for custom namespaces

## CLI Reference

```bash
# Add namespaced memory
memory-tool add <category> "<content>" --wing <wing> --room <room>

# Check access
memory-tool check-access <wing> <room> --passport-file <path>

# List access rules
memory-tool access-rules

# Search with access filtering (programmatic)
# See memory_tool/access_control.py for filter_memories_by_access()
```

## See Also

- [Passport System](memory_tool/passport.py) - Complete memory identity cards
- [Memory Tiers](memory_tool/tiers.py) - Working/Episodic/Semantic classification
- [Graph Intelligence](memory_tool/graph.py) - Entity relationships
