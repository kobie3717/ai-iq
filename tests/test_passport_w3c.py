"""Tests for W3C Verifiable Credentials passport system."""

import pytest
import json
import base64
from datetime import datetime, timedelta

try:
    from memory_tool.passport_w3c import (
        generate_keypair,
        classify_task_domain,
        calculate_competence_from_db,
        issue_credential,
        verify_credential,
        sign_data,
        verify_signature,
        has_crypto_support,
        COMPETENCE_DOMAINS,
        DOMAIN_KEYWORDS,
    )
    _IMPORTS_AVAILABLE = True
except ImportError:
    _IMPORTS_AVAILABLE = False


@pytest.mark.skipif(not _IMPORTS_AVAILABLE or not has_crypto_support(),
                   reason="cryptography library not available")
class TestPassportW3C:
    """Tests for W3C passport credential system."""

    def test_generate_keypair(self):
        """Test Ed25519 keypair generation."""
        private_key, public_key = generate_keypair()

        assert len(private_key) == 32  # Ed25519 private key is 32 bytes
        assert len(public_key) == 32   # Ed25519 public key is 32 bytes
        assert private_key != public_key

    def test_classify_task_domain_code(self):
        """Test domain classification for code tasks."""
        domain = classify_task_domain("Implement user module with new features")
        assert domain == "code"

        domain = classify_task_domain("Fix bug in payment refactor module", "backend,api")
        assert domain == "code"

    def test_classify_task_domain_devops(self):
        """Test domain classification for devops tasks."""
        domain = classify_task_domain("Deploy application to production server")
        assert domain == "devops"

        domain = classify_task_domain("Configure nginx reverse proxy", "nginx,server")
        assert domain == "devops"

    def test_classify_task_domain_security(self):
        """Test domain classification for security tasks."""
        domain = classify_task_domain("Fix SQL injection vulnerability in auth")
        assert domain == "security"

        domain = classify_task_domain("Audit JWT token encryption", "security,audit")
        assert domain == "security"

    def test_classify_task_domain_testing(self):
        """Test domain classification for testing tasks."""
        domain = classify_task_domain("Write pytest unit tests for API")
        assert domain == "testing"

        domain = classify_task_domain("Add integration test coverage", "testing,qa")
        assert domain == "testing"

    def test_classify_task_domain_fallback(self):
        """Test domain classification falls back to 'code' for ambiguous tasks."""
        domain = classify_task_domain("Do something")
        assert domain == "code"

    def test_calculate_competence_empty_db(self, temp_db):
        """Test competence calculation with empty database."""
        competence = calculate_competence_from_db(temp_db)

        assert len(competence) == len(COMPETENCE_DOMAINS)
        for domain in COMPETENCE_DOMAINS:
            assert domain in competence
            assert 0.0 <= competence[domain] <= 1.0
            # Empty DB should have baseline scores
            assert competence[domain] == 0.1

    def test_calculate_competence_with_runs(self, temp_db):
        """Test competence calculation with runs data."""
        # Insert test runs
        temp_db.execute("""
            INSERT INTO runs (task, status, outcome, tags)
            VALUES
            ('Implement auth API', 'completed', 'success - tests passing', 'backend,api'),
            ('Deploy to prod', 'completed', 'done - server running', 'devops'),
            ('Fix SQL injection', 'completed', 'fixed vulnerability', 'security'),
            ('Write unit tests', 'completed', 'coverage improved', 'testing')
        """)
        temp_db.commit()

        competence = calculate_competence_from_db(temp_db)

        # Should have all domains present
        assert set(competence.keys()) == set(COMPETENCE_DOMAINS)
        # All scores should be in valid range
        assert all(0.0 <= score <= 1.0 for score in competence.values())
        # Domains with completed tasks should have non-zero scores
        assert competence['code'] > 0.0
        assert competence['devops'] > 0.0
        assert competence['testing'] > 0.0

    def test_calculate_competence_with_memories(self, temp_db):
        """Test competence calculation includes relevant memories."""
        temp_db.execute("""
            INSERT INTO memories (category, content, tags, active)
            VALUES
            ('learning', 'Learned React hooks patterns', 'frontend,code', 1),
            ('decision', 'Use Docker for deployment', 'devops,docker', 1),
            ('project', 'Security audit complete', 'security', 1)
        """)
        temp_db.commit()

        competence = calculate_competence_from_db(temp_db)

        # Should return all expected domains
        assert set(competence.keys()) == set(COMPETENCE_DOMAINS)
        # All scores should be in valid range
        assert all(0.0 <= score <= 1.0 for score in competence.values())

    def test_sign_and_verify(self):
        """Test Ed25519 signing and verification."""
        private_key, public_key = generate_keypair()
        data = b"test data to sign"

        signature = sign_data(data, private_key)

        assert len(signature) == 64  # Ed25519 signatures are 64 bytes
        assert verify_signature(data, signature, public_key) is True

    def test_verify_signature_tampered_data(self):
        """Test signature verification fails for tampered data."""
        private_key, public_key = generate_keypair()
        data = b"original data"
        signature = sign_data(data, private_key)

        tampered_data = b"tampered data"
        assert verify_signature(tampered_data, signature, public_key) is False

    def test_verify_signature_wrong_key(self):
        """Test signature verification fails with wrong public key."""
        private_key1, public_key1 = generate_keypair()
        private_key2, public_key2 = generate_keypair()

        data = b"test data"
        signature = sign_data(data, private_key1)

        # Should fail with wrong public key
        assert verify_signature(data, signature, public_key2) is False

    def test_issue_credential_structure(self, temp_db):
        """Test credential has correct W3C structure."""
        private_key, public_key = generate_keypair()

        competence = {domain: 0.5 for domain in COMPETENCE_DOMAINS}
        proof_of_work = {
            "tasksCompleted": {"code": 10, "devops": 5},
            "totalTasks": 15,
            "verifiedOutcomes": 12
        }

        credential = issue_credential(
            agent_id="test-agent-001",
            competence_scores=competence,
            proof_of_work=proof_of_work,
            private_key_bytes=private_key,
            public_key_bytes=public_key,
            validity_days=90
        )

        # Check W3C structure
        assert "@context" in credential
        assert "https://www.w3.org/2018/credentials/v1" in credential["@context"]
        assert credential["type"] == ["VerifiableCredential", "AgentPassport"]

        # Check DID format
        assert credential["issuer"].startswith("did:key:")
        assert credential["credentialSubject"]["id"] == "did:agent:test-agent-001"

        # Check dates
        assert "issuanceDate" in credential
        assert "expirationDate" in credential

        # Check subject data
        subject = credential["credentialSubject"]
        assert "competence" in subject
        assert "proofOfWork" in subject
        assert subject["competence"] == competence
        assert subject["proofOfWork"] == proof_of_work

        # Check proof
        assert "proof" in credential
        assert credential["proof"]["type"] == "Ed25519Signature2020"
        assert "proofValue" in credential["proof"]

    def test_issue_credential_expiration(self, temp_db):
        """Test credential expiration date is calculated correctly."""
        private_key, public_key = generate_keypair()

        competence = {domain: 0.5 for domain in COMPETENCE_DOMAINS}
        proof_of_work = {"tasksCompleted": {}, "totalTasks": 0, "verifiedOutcomes": 0}

        credential = issue_credential(
            agent_id="test-agent",
            competence_scores=competence,
            proof_of_work=proof_of_work,
            private_key_bytes=private_key,
            public_key_bytes=public_key,
            validity_days=30
        )

        issued = datetime.fromisoformat(credential["issuanceDate"].replace("Z", ""))
        expires = datetime.fromisoformat(credential["expirationDate"].replace("Z", ""))

        delta = (expires - issued).days
        assert delta == 30

    def test_verify_credential_valid(self, temp_db):
        """Test verification succeeds for valid credential."""
        private_key, public_key = generate_keypair()

        competence = {domain: 0.5 for domain in COMPETENCE_DOMAINS}
        proof_of_work = {"tasksCompleted": {}, "totalTasks": 0, "verifiedOutcomes": 0}

        credential = issue_credential(
            agent_id="test-agent",
            competence_scores=competence,
            proof_of_work=proof_of_work,
            private_key_bytes=private_key,
            public_key_bytes=public_key
        )

        # Should verify with correct public key
        assert verify_credential(credential, public_key) is True

    def test_verify_credential_tampered(self, temp_db):
        """Test verification fails for tampered credential."""
        private_key, public_key = generate_keypair()

        competence = {domain: 0.5 for domain in COMPETENCE_DOMAINS}
        proof_of_work = {"tasksCompleted": {}, "totalTasks": 0, "verifiedOutcomes": 0}

        credential = issue_credential(
            agent_id="test-agent",
            competence_scores=competence,
            proof_of_work=proof_of_work,
            private_key_bytes=private_key,
            public_key_bytes=public_key
        )

        # Tamper with credential
        credential["credentialSubject"]["competence"]["code"] = 1.0

        # Should fail verification
        assert verify_credential(credential, public_key) is False

    def test_verify_credential_wrong_key(self, temp_db):
        """Test verification fails with wrong public key."""
        private_key1, public_key1 = generate_keypair()
        private_key2, public_key2 = generate_keypair()

        competence = {domain: 0.5 for domain in COMPETENCE_DOMAINS}
        proof_of_work = {"tasksCompleted": {}, "totalTasks": 0, "verifiedOutcomes": 0}

        credential = issue_credential(
            agent_id="test-agent",
            competence_scores=competence,
            proof_of_work=proof_of_work,
            private_key_bytes=private_key1,
            public_key_bytes=public_key1
        )

        # Should fail with wrong key
        assert verify_credential(credential, public_key2) is False

    def test_verify_credential_no_proof(self, temp_db):
        """Test verification fails for credential without proof."""
        credential = {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "type": ["VerifiableCredential"],
            "credentialSubject": {}
        }

        private_key, public_key = generate_keypair()
        assert verify_credential(credential, public_key) is False


@pytest.mark.skipif(_IMPORTS_AVAILABLE and has_crypto_support(),
                   reason="only run when crypto not available")
def test_no_crypto_library():
    """Test graceful handling when cryptography not installed."""
    assert not has_crypto_support()
