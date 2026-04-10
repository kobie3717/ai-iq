"""
Capability-Based Access Control for Memory Namespaces.

Controls access to memories based on wing/room namespaces and passport credentials.
Uses deny-by-default security model where undefined namespaces are blocked.

Example:
    passport = {
        'credentialSubject': {
            'competence': {'code': 0.9, 'security': 0.7, 'devops': 0.8}
        }
    }

    # Check access to finance.payments namespace
    allowed, reason = check_access('finance', 'payments', passport)
    if allowed:
        # Access granted
    else:
        print(f"Access denied: {reason}")
"""

from typing import Optional, Dict, Any, List, Tuple

from .config import get_logger

logger = get_logger(__name__)

# Predefined access rules for memory namespaces
# Format: 'wing.room': {'min_competence': {domain: score}, 'description': str}
ACCESS_RULES = {
    'finance.payments': {
        'min_competence': {'code': 0.6, 'security': 0.5},
        'description': 'Payment processing code and configs'
    },
    'security.secrets': {
        'min_competence': {'security': 0.8},
        'description': 'Credentials and keys'
    },
    'devops.production': {
        'min_competence': {'devops': 0.7, 'security': 0.5},
        'description': 'Production deployment configs'
    },
    'code.internal': {
        'min_competence': {'code': 0.5},
        'description': 'Internal codebase access'
    },
    'general.public': {
        'min_competence': {},
        'description': 'Publicly accessible knowledge'
    }
}


def check_access(
    wing: Optional[str],
    room: Optional[str],
    passport_credential: Optional[Dict[str, Any]]
) -> Tuple[bool, str]:
    """
    Check if a passport credential grants access to a wing/room namespace.

    Args:
        wing: Namespace wing (e.g., 'finance', 'security')
        room: Namespace room (e.g., 'payments', 'secrets')
        passport_credential: Passport credential dict with competence scores
                            Format: {'credentialSubject': {'competence': {domain: score}}}

    Returns:
        (allowed: bool, reason: str) - True if access granted, False with reason if denied

    Access Logic:
        1. If no wing/room specified -> allow (general access)
        2. If namespace not in ACCESS_RULES -> deny (deny-by-default)
        3. If rule has empty min_competence -> allow (public namespace)
        4. If no passport provided -> deny (authentication required)
        5. Check each required domain score against passport competence
        6. All thresholds must be met -> allow, any fail -> deny
    """
    # No namespace specified -> general access allowed
    if not wing or not room:
        return True, "No namespace restriction"

    # Build namespace key
    namespace = f"{wing}.{room}"

    # Check if namespace has defined rule
    if namespace not in ACCESS_RULES:
        return False, f"Undefined namespace '{namespace}' (deny-by-default)"

    rule = ACCESS_RULES[namespace]
    min_competence = rule['min_competence']

    # Public namespace (no competence required)
    if not min_competence:
        return True, f"Public namespace '{namespace}'"

    # Authentication required but no passport provided
    if not passport_credential:
        return False, f"Authentication required for '{namespace}'"

    # Extract competence scores from passport
    try:
        credential_subject = passport_credential.get('credentialSubject', {})
        competence = credential_subject.get('competence', {})

        # Validate that competence is actually present (not just empty dict)
        if not isinstance(competence, dict):
            return False, "Invalid passport format (competence must be a dict)"

        # If competence is empty dict but min_competence is required, it's invalid
        if not competence and min_competence:
            return False, "Invalid passport format (missing competence scores)"

    except (AttributeError, TypeError):
        return False, "Invalid passport format (missing credentialSubject.competence)"

    # Check each required domain threshold
    insufficient = []
    for domain, required_score in min_competence.items():
        actual_score = competence.get(domain, 0.0)

        if actual_score < required_score:
            insufficient.append(
                f"{domain}: {actual_score:.2f} < {required_score:.2f}"
            )

    # All thresholds met -> access granted
    if not insufficient:
        return True, f"Competence requirements met for '{namespace}'"

    # Some thresholds not met -> access denied
    reason = f"Insufficient competence for '{namespace}': " + ", ".join(insufficient)
    return False, reason


def filter_memories_by_access(
    rows: List[Dict[str, Any]],
    passport_credential: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Filter a list of memory rows based on access control rules.

    Args:
        rows: List of memory dicts (each must have 'wing' and 'room' keys)
        passport_credential: Passport credential for access checks

    Returns:
        Filtered list containing only memories that pass access control

    Note:
        Memories without wing/room (general access) always pass through.
    """
    filtered = []

    for row in rows:
        wing = row.get('wing')
        room = row.get('room')

        # No namespace -> general access, always include
        if not wing or not room:
            filtered.append(row)
            continue

        # Check access for namespaced memory
        allowed, reason = check_access(wing, room, passport_credential)

        if allowed:
            filtered.append(row)
        else:
            # Log denied access attempts for security audit
            logger.debug(
                f"Access denied to memory #{row.get('id', '?')} "
                f"({wing}.{room}): {reason}"
            )

    return filtered


def list_rules() -> str:
    """
    Return formatted string of all access control rules.

    Returns:
        Multi-line string with rule details
    """
    if not ACCESS_RULES:
        return "No access rules defined."

    lines = ["Access Control Rules:", "=" * 70]

    for namespace, rule in sorted(ACCESS_RULES.items()):
        lines.append(f"\n{namespace}")
        lines.append(f"  Description: {rule['description']}")

        min_comp = rule['min_competence']
        if not min_comp:
            lines.append("  Access: PUBLIC (no competence required)")
        else:
            lines.append("  Required Competence:")
            for domain, score in sorted(min_comp.items()):
                lines.append(f"    - {domain}: {score:.2f}")

    lines.append("\n" + "=" * 70)
    lines.append("\nDeny-by-default: All undefined namespaces are blocked.")

    return "\n".join(lines)


def cmd_check_access(args) -> None:
    """
    CLI handler for checking access to a namespace.

    Usage:
        memory-tool check-access finance payments --passport-file passport.json

    Args:
        args: Parsed CLI arguments with wing, room, passport_file
    """
    import json
    import sys

    wing = args.wing
    room = args.room

    # Load passport from file if provided
    passport = None
    if hasattr(args, 'passport_file') and args.passport_file:
        try:
            with open(args.passport_file, 'r') as f:
                passport = json.load(f)
        except FileNotFoundError:
            print(f"Error: Passport file not found: {args.passport_file}", file=sys.stderr)
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in passport file: {e}", file=sys.stderr)
            sys.exit(1)

    # Check access
    allowed, reason = check_access(wing, room, passport)

    # Output result
    namespace = f"{wing}.{room}"
    if allowed:
        print(f"✓ ACCESS GRANTED to '{namespace}'")
        print(f"  Reason: {reason}")
        sys.exit(0)
    else:
        print(f"✗ ACCESS DENIED to '{namespace}'")
        print(f"  Reason: {reason}")
        sys.exit(1)


def cmd_access_rules(args) -> None:
    """
    CLI handler for listing all access control rules.

    Usage:
        memory-tool access-rules

    Args:
        args: Parsed CLI arguments (unused)
    """
    print(list_rules())
