"""
W3C Verifiable Credentials for Agent Passports.

Issues cryptographic credentials that prove an agent's competence across domains
based on verified task completion (proof-of-work). Uses Ed25519 signatures for
verifiable credentials following W3C VC Data Model.

Competence Domains:
- code: implementation, refactoring, bug fixes
- devops: deployment, infrastructure, production ops
- security: auth, vulnerabilities, encryption
- testing: test writing, QA, validation
- documentation: docs, specs, guides
- research: analysis, investigation, benchmarking
- planning: architecture, design, strategy
- monitoring: observability, alerts, health checks
"""

import json
import base64
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False

from .config import get_logger
from .database import get_db

logger = get_logger(__name__)


COMPETENCE_DOMAINS = [
    'code', 'devops', 'security', 'testing',
    'documentation', 'research', 'planning', 'monitoring'
]

DOMAIN_KEYWORDS = {
    'code': ['coding', 'refactor', 'bug-fix', 'implementation', 'feature', 'api',
             'frontend', 'backend', 'debug', 'function', 'class', 'module'],
    'devops': ['deploy', 'docker', 'nginx', 'systemd', 'production', 'pm2',
               'server', 'infra', 'kubernetes', 'ci', 'cd', 'pipeline'],
    'security': ['auth', 'vulnerability', 'encryption', 'audit', 'credentials',
                 'ssl', 'jwt', 'xss', 'sql-injection', 'authentication'],
    'testing': ['test', 'pytest', 'jest', 'coverage', 'qa', 'validation',
                'unit-test', 'integration', 'e2e'],
    'documentation': ['docs', 'readme', 'spec', 'guide', 'documentation',
                     'manual', 'tutorial', 'api-docs'],
    'research': ['research', 'analysis', 'investigate', 'benchmark', 'compare',
                 'study', 'evaluate', 'survey'],
    'planning': ['plan', 'architecture', 'design', 'roadmap', 'strategy',
                 'schema', 'blueprint', 'system-design'],
    'monitoring': ['monitor', 'alert', 'logs', 'health', 'uptime', 'observability',
                   'metrics', 'tracing', 'logging']
}


def has_crypto_support() -> bool:
    """Check if cryptography library is available."""
    return _CRYPTO_AVAILABLE


def generate_keypair() -> Tuple[bytes, bytes]:
    """
    Generate Ed25519 private/public key pair.

    Returns:
        (private_key_bytes, public_key_bytes) tuple

    Raises:
        ImportError: If cryptography library not available
    """
    if not has_crypto_support():
        raise ImportError("cryptography library required for passport credentials")

    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Serialize to raw bytes
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )

    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )

    return private_bytes, public_bytes


def classify_task_domain(task_description: str, tags: Optional[str] = None) -> str:
    """
    Classify a task into best matching domain based on keywords.

    Args:
        task_description: Task description text
        tags: Optional comma-separated tags

    Returns:
        Best matching domain name (from COMPETENCE_DOMAINS)
    """
    text = (task_description + " " + (tags or "")).lower()

    # Count keyword matches per domain
    scores = defaultdict(int)
    for domain, keywords in DOMAIN_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                scores[domain] += 1

    if not scores:
        return 'code'  # default

    # Return domain with highest score
    return max(scores.items(), key=lambda x: x[1])[0]


def calculate_competence_from_db(conn: sqlite3.Connection) -> Dict[str, float]:
    """
    Calculate competence scores per domain from runs and memories.

    Score calculation:
    - Completed tasks: 1.0 weight per task
    - Success rate: ratio of successful completions
    - Normalized to 0.0-1.0 range per domain

    Args:
        conn: Database connection

    Returns:
        Dict mapping domain -> competence score (0.0-1.0)
    """
    competence = {domain: 0.0 for domain in COMPETENCE_DOMAINS}

    # Get runs with domains (if domain column exists)
    runs = []
    try:
        runs = conn.execute("""
            SELECT task, status, outcome, tags, domain
            FROM runs
            WHERE status = 'completed'
        """).fetchall()
    except sqlite3.OperationalError as e:
        # Table doesn't exist or domain column doesn't exist
        try:
            runs = conn.execute("""
                SELECT task, status, outcome, tags, NULL as domain
                FROM runs
                WHERE status = 'completed'
            """).fetchall()
        except sqlite3.OperationalError:
            # runs table doesn't exist at all
            runs = []

    # Count tasks per domain
    domain_counts = defaultdict(int)
    domain_successes = defaultdict(int)

    for run in runs:
        domain = run['domain'] if run['domain'] else classify_task_domain(run['task'], run['tags'])
        domain_counts[domain] += 1

        # Check if outcome indicates success
        outcome = (run['outcome'] or '').lower()
        if any(word in outcome for word in ['success', 'completed', 'done', 'fixed', 'passed']):
            domain_successes[domain] += 1

    # Also count relevant memories per domain (use tags/content)
    memories = []
    try:
        memories = conn.execute("""
            SELECT category, content, tags
            FROM memories
            WHERE active = 1 AND category IN ('learning', 'decision', 'project')
        """).fetchall()
    except sqlite3.OperationalError:
        # memories table doesn't exist
        memories = []

    for mem in memories:
        text = f"{mem['category']} {mem['content']} {mem['tags']}"
        domain = classify_task_domain(text)
        domain_counts[domain] += 0.5  # memories count for less than tasks

    # Calculate normalized scores (0.0-1.0)
    max_count = max(domain_counts.values()) if domain_counts else 1

    for domain in COMPETENCE_DOMAINS:
        if domain_counts[domain] > 0:
            # Base score from task count
            count_score = min(1.0, domain_counts[domain] / max(max_count, 10))

            # Success rate modifier
            success_rate = domain_successes[domain] / domain_counts[domain] if domain_counts[domain] > 0 else 0.5

            # Combined score (weighted average)
            competence[domain] = (count_score * 0.7) + (success_rate * 0.3)
        else:
            competence[domain] = 0.1  # baseline for untested domains

    return competence


def sign_data(data: bytes, private_key_bytes: bytes) -> bytes:
    """
    Sign data with Ed25519 private key.

    Args:
        data: Bytes to sign
        private_key_bytes: 32-byte private key

    Returns:
        64-byte signature
    """
    if not has_crypto_support():
        raise ImportError("cryptography library required")

    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    signature = private_key.sign(data)
    return signature


def verify_signature(data: bytes, signature: bytes, public_key_bytes: bytes) -> bool:
    """
    Verify Ed25519 signature.

    Args:
        data: Original data that was signed
        signature: Signature bytes
        public_key_bytes: 32-byte public key

    Returns:
        True if signature is valid
    """
    if not has_crypto_support():
        raise ImportError("cryptography library required")

    try:
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(signature, data)
        return True
    except Exception as e:
        logger.debug(f"Signature verification failed: {e}")
        return False


def issue_credential(
    agent_id: str,
    competence_scores: Dict[str, float],
    proof_of_work: Dict[str, Any],
    private_key_bytes: bytes,
    public_key_bytes: bytes,
    validity_days: int = 90
) -> Dict[str, Any]:
    """
    Issue a W3C Verifiable Credential for agent passport.

    Args:
        agent_id: Agent identifier (e.g., 'claude-001')
        competence_scores: Dict mapping domain -> score (0.0-1.0)
        proof_of_work: Dict with tasksCompleted, totalTasks, verifiedOutcomes
        private_key_bytes: 32-byte private key for signing
        public_key_bytes: 32-byte public key
        validity_days: Credential validity period (default 90 days)

    Returns:
        W3C VC JSON structure with proof
    """
    if not has_crypto_support():
        raise ImportError("cryptography library required")

    now = datetime.utcnow()
    expiration = now + timedelta(days=validity_days)

    # Build DID for issuer (did:key format using public key)
    pubkey_b64 = base64.b64encode(public_key_bytes).decode('ascii')
    issuer_did = f"did:key:{pubkey_b64}"

    # Build credential without proof first
    credential = {
        "@context": ["https://www.w3.org/2018/credentials/v1"],
        "type": ["VerifiableCredential", "AgentPassport"],
        "issuer": issuer_did,
        "issuanceDate": now.isoformat() + "Z",
        "expirationDate": expiration.isoformat() + "Z",
        "credentialSubject": {
            "id": f"did:agent:{agent_id}",
            "competence": competence_scores,
            "proofOfWork": proof_of_work
        }
    }

    # Create canonical JSON for signing (sorted keys, no whitespace)
    canonical = json.dumps(credential, sort_keys=True, separators=(',', ':'))
    signature = sign_data(canonical.encode('utf-8'), private_key_bytes)

    # Add proof
    credential["proof"] = {
        "type": "Ed25519Signature2020",
        "created": now.isoformat() + "Z",
        "proofPurpose": "assertionMethod",
        "verificationMethod": issuer_did,
        "proofValue": base64.b64encode(signature).decode('ascii')
    }

    return credential


def verify_credential(credential: Dict[str, Any], public_key_bytes: bytes) -> bool:
    """
    Verify a W3C Verifiable Credential signature.

    Args:
        credential: W3C VC JSON structure
        public_key_bytes: 32-byte public key

    Returns:
        True if credential is valid and signature matches
    """
    if not has_crypto_support():
        raise ImportError("cryptography library required")

    # Extract proof
    proof = credential.get("proof")
    if not proof:
        logger.error("No proof found in credential")
        return False

    # Remove proof to recreate canonical form
    credential_without_proof = {k: v for k, v in credential.items() if k != "proof"}
    canonical = json.dumps(credential_without_proof, sort_keys=True, separators=(',', ':'))

    # Decode signature
    try:
        signature = base64.b64decode(proof["proofValue"])
    except Exception as e:
        logger.error(f"Failed to decode proof signature: {e}")
        return False

    # Verify signature
    return verify_signature(canonical.encode('utf-8'), signature, public_key_bytes)


def cmd_passport(args: List[str], conn: sqlite3.Connection) -> None:
    """
    CLI handler for generating agent passport credentials.

    Usage:
        memory-tool passport [--agent-id ID] [--output FILE]
    """
    if not has_crypto_support():
        print("Error: cryptography library not installed")
        print("Install with: pip install cryptography")
        return

    # Parse flags
    agent_id = "claude-001"
    output_file = None

    i = 0
    while i < len(args):
        if args[i] == "--agent-id" and i + 1 < len(args):
            agent_id = args[i + 1]
            i += 2
        elif args[i] == "--output" and i + 1 < len(args):
            output_file = args[i + 1]
            i += 2
        else:
            i += 1

    # Generate keypair
    print(f"Generating passport credential for agent: {agent_id}")
    private_key, public_key = generate_keypair()

    # Calculate competence scores
    competence = calculate_competence_from_db(conn)

    # Collect proof-of-work stats
    total_tasks = conn.execute("SELECT COUNT(*) as c FROM runs WHERE status = 'completed'").fetchone()['c']

    tasks_by_domain = defaultdict(int)
    try:
        runs = conn.execute("SELECT domain FROM runs WHERE status = 'completed' AND domain IS NOT NULL").fetchall()
        for run in runs:
            tasks_by_domain[run['domain']] += 1
    except sqlite3.OperationalError:
        pass  # domain column doesn't exist

    # Count successful outcomes
    verified = conn.execute("""
        SELECT COUNT(*) as c FROM runs
        WHERE status = 'completed'
        AND (outcome LIKE '%success%' OR outcome LIKE '%completed%' OR outcome LIKE '%done%')
    """).fetchone()['c']

    proof_of_work = {
        "tasksCompleted": dict(tasks_by_domain) if tasks_by_domain else {d: 0 for d in COMPETENCE_DOMAINS},
        "totalTasks": total_tasks,
        "verifiedOutcomes": verified
    }

    # Issue credential
    credential = issue_credential(
        agent_id=agent_id,
        competence_scores=competence,
        proof_of_work=proof_of_work,
        private_key_bytes=private_key,
        public_key_bytes=public_key
    )

    # Save to database
    credential_json = json.dumps(credential, indent=2)
    expiration = credential['expirationDate']

    cursor = conn.execute("""
        INSERT INTO passport_credentials (agent_id, credential_json, public_key, expires_at)
        VALUES (?, ?, ?, ?)
    """, (agent_id, credential_json, public_key, expiration))
    conn.commit()
    credential_id = cursor.lastrowid

    # Display summary
    print("\n🪪 PASSPORT CREDENTIAL ISSUED")
    print("=" * 70)
    print(f"Agent ID: {agent_id}")
    print(f"Issued: {credential['issuanceDate']}")
    print(f"Expires: {credential['expirationDate']}")
    print(f"\nCompetence Scores:")
    for domain, score in sorted(competence.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(score * 20)
        print(f"  {domain:15} {score:.2f} {bar}")

    print(f"\nProof of Work:")
    print(f"  Total Tasks: {proof_of_work['totalTasks']}")
    print(f"  Verified Outcomes: {proof_of_work['verifiedOutcomes']}")

    # Output to file if requested
    if output_file:
        with open(output_file, 'w') as f:
            f.write(credential_json)
        print(f"\nCredential saved to: {output_file}")
        print(f"Public key (base64): {base64.b64encode(public_key).decode()}")

    print("=" * 70)
    print(f"\nCredential stored in database (ID: {credential_id})")


def cmd_verify_passport(args: List[str], conn: sqlite3.Connection) -> None:
    """
    CLI handler for verifying passport credentials.

    Usage:
        memory-tool verify-passport <credential_file>
    """
    if not has_crypto_support():
        print("Error: cryptography library not installed")
        return

    if len(args) < 1:
        print("Usage: memory-tool verify-passport <credential_file>")
        return

    credential_file = args[0]

    try:
        with open(credential_file, 'r') as f:
            credential = json.load(f)
    except Exception as e:
        print(f"Error reading credential file: {e}")
        return

    # Extract public key from issuer DID
    issuer_did = credential.get('issuer', '')
    if not issuer_did.startswith('did:key:'):
        print("Error: Invalid issuer DID format")
        return

    pubkey_b64 = issuer_did.replace('did:key:', '')
    try:
        public_key = base64.b64decode(pubkey_b64)
    except Exception as e:
        print(f"Error decoding public key: {e}")
        return

    # Verify signature
    valid = verify_credential(credential, public_key)

    print("\n🔐 PASSPORT VERIFICATION")
    print("=" * 70)
    print(f"Agent ID: {credential['credentialSubject']['id']}")
    print(f"Issued: {credential['issuanceDate']}")
    print(f"Expires: {credential['expirationDate']}")
    print(f"Signature: {'✓ VALID' if valid else '✗ INVALID'}")

    if valid:
        print("\nCompetence Scores:")
        competence = credential['credentialSubject']['competence']
        for domain, score in sorted(competence.items(), key=lambda x: x[1], reverse=True):
            bar = "█" * int(score * 20)
            print(f"  {domain:15} {score:.2f} {bar}")

        pow_data = credential['credentialSubject']['proofOfWork']
        print(f"\nProof of Work:")
        print(f"  Total Tasks: {pow_data['totalTasks']}")
        print(f"  Verified Outcomes: {pow_data['verifiedOutcomes']}")

    print("=" * 70)
