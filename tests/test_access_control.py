"""Tests for capability-based access control."""

import pytest
from memory_tool.access_control import (
    check_access,
    filter_memories_by_access,
    list_rules,
    ACCESS_RULES
)


# Mock passport credentials for testing
MOCK_HIGH_PASSPORT = {
    "credentialSubject": {
        "competence": {
            "code": 0.9,
            "devops": 0.8,
            "security": 0.7,
            "testing": 0.6,
            "documentation": 0.5
        }
    }
}

MOCK_LOW_PASSPORT = {
    "credentialSubject": {
        "competence": {
            "code": 0.3,
            "devops": 0.2,
            "security": 0.1,
            "testing": 0.4,
            "documentation": 0.6
        }
    }
}

MOCK_MID_PASSPORT = {
    "credentialSubject": {
        "competence": {
            "code": 0.6,
            "devops": 0.5,
            "security": 0.5,
            "testing": 0.7
        }
    }
}


def test_access_granted_high_competence():
    """Access granted when competence exceeds all thresholds."""
    # finance.payments requires code: 0.6, security: 0.5
    allowed, reason = check_access('finance', 'payments', MOCK_HIGH_PASSPORT)
    assert allowed is True
    assert 'Competence requirements met' in reason


def test_access_granted_exact_threshold():
    """Access granted when competence exactly meets thresholds."""
    # finance.payments requires code: 0.6, security: 0.5
    allowed, reason = check_access('finance', 'payments', MOCK_MID_PASSPORT)
    assert allowed is True
    assert 'Competence requirements met' in reason


def test_access_denied_insufficient_competence():
    """Access denied when competence below threshold."""
    # security.secrets requires security: 0.8
    # MOCK_LOW_PASSPORT has security: 0.1
    allowed, reason = check_access('security', 'secrets', MOCK_LOW_PASSPORT)
    assert allowed is False
    assert 'Insufficient competence' in reason
    assert 'security: 0.10 < 0.80' in reason


def test_access_denied_multiple_insufficient():
    """Access denied with correct reason when multiple domains insufficient."""
    # devops.production requires devops: 0.7, security: 0.5
    # MOCK_LOW_PASSPORT has devops: 0.2, security: 0.1
    allowed, reason = check_access('devops', 'production', MOCK_LOW_PASSPORT)
    assert allowed is False
    assert 'Insufficient competence' in reason
    # Both domains should be listed as insufficient
    assert 'devops:' in reason
    assert 'security:' in reason


def test_public_namespace_always_accessible():
    """Public namespace accessible with any or no passport."""
    # general.public has empty min_competence
    allowed, reason = check_access('general', 'public', None)
    assert allowed is True
    assert 'Public namespace' in reason

    allowed, reason = check_access('general', 'public', MOCK_LOW_PASSPORT)
    assert allowed is True
    assert 'Public namespace' in reason

    allowed, reason = check_access('general', 'public', MOCK_HIGH_PASSPORT)
    assert allowed is True
    assert 'Public namespace' in reason


def test_undefined_namespace_denied_by_default():
    """Undefined namespace denied by default (security)."""
    allowed, reason = check_access('unknown', 'namespace', MOCK_HIGH_PASSPORT)
    assert allowed is False
    assert 'Undefined namespace' in reason
    assert 'deny-by-default' in reason


def test_no_namespace_always_allowed():
    """Memories without wing/room always pass through (general access)."""
    # No wing/room -> general access
    allowed, reason = check_access(None, None, None)
    assert allowed is True
    assert 'No namespace restriction' in reason

    allowed, reason = check_access('finance', None, MOCK_HIGH_PASSPORT)
    assert allowed is True
    assert 'No namespace restriction' in reason

    allowed, reason = check_access(None, 'payments', MOCK_HIGH_PASSPORT)
    assert allowed is True
    assert 'No namespace restriction' in reason


def test_no_passport_for_restricted_namespace():
    """Access denied when passport required but not provided."""
    # code.internal requires code: 0.5
    allowed, reason = check_access('code', 'internal', None)
    assert allowed is False
    assert 'Authentication required' in reason


def test_invalid_passport_format():
    """Access denied with helpful error for malformed passport."""
    invalid_passport = {"wrong_key": "value"}
    allowed, reason = check_access('code', 'internal', invalid_passport)
    assert allowed is False
    assert 'Invalid passport format' in reason

    # Passport is not a dict
    allowed, reason = check_access('code', 'internal', "not_a_dict")
    assert allowed is False
    assert 'Invalid passport format' in reason


def test_filter_memories_by_access_mixed():
    """Filter memories with mixed wing/room namespaces."""
    memories = [
        {'id': 1, 'content': 'Public data', 'wing': None, 'room': None},
        {'id': 2, 'content': 'Payment config', 'wing': 'finance', 'room': 'payments'},
        {'id': 3, 'content': 'Secret key', 'wing': 'security', 'room': 'secrets'},
        {'id': 4, 'content': 'General info', 'wing': 'general', 'room': 'public'},
        {'id': 5, 'content': 'Code snippet', 'wing': 'code', 'room': 'internal'},
    ]

    # High passport should access all except security.secrets (requires 0.8, has 0.7)
    filtered = filter_memories_by_access(memories, MOCK_HIGH_PASSPORT)
    filtered_ids = [m['id'] for m in filtered]
    assert 1 in filtered_ids  # No namespace
    assert 2 in filtered_ids  # finance.payments (0.9 code, 0.7 security > 0.6, 0.5)
    assert 3 not in filtered_ids  # security.secrets (0.7 < 0.8)
    assert 4 in filtered_ids  # general.public (public)
    assert 5 in filtered_ids  # code.internal (0.9 > 0.5)


def test_filter_memories_by_access_low_passport():
    """Low competence passport filters out most restricted memories."""
    memories = [
        {'id': 1, 'content': 'Public data', 'wing': None, 'room': None},
        {'id': 2, 'content': 'Payment config', 'wing': 'finance', 'room': 'payments'},
        {'id': 3, 'content': 'General info', 'wing': 'general', 'room': 'public'},
    ]

    filtered = filter_memories_by_access(memories, MOCK_LOW_PASSPORT)
    filtered_ids = [m['id'] for m in filtered]
    assert 1 in filtered_ids  # No namespace
    assert 2 not in filtered_ids  # finance.payments (0.3 code, 0.1 security < 0.6, 0.5)
    assert 3 in filtered_ids  # general.public (public)


def test_filter_memories_no_passport():
    """No passport only allows general access and public namespaces."""
    memories = [
        {'id': 1, 'content': 'Public data', 'wing': None, 'room': None},
        {'id': 2, 'content': 'Payment config', 'wing': 'finance', 'room': 'payments'},
        {'id': 3, 'content': 'General info', 'wing': 'general', 'room': 'public'},
        {'id': 4, 'content': 'Code snippet', 'wing': 'code', 'room': 'internal'},
    ]

    filtered = filter_memories_by_access(memories, None)
    filtered_ids = [m['id'] for m in filtered]
    assert 1 in filtered_ids  # No namespace
    assert 2 not in filtered_ids  # finance.payments requires passport
    assert 3 in filtered_ids  # general.public (public)
    assert 4 not in filtered_ids  # code.internal requires passport


def test_filter_memories_empty_list():
    """Filter handles empty memory list."""
    filtered = filter_memories_by_access([], MOCK_HIGH_PASSPORT)
    assert filtered == []


def test_list_rules_output():
    """List rules returns formatted string with all rules."""
    output = list_rules()

    # Check structure
    assert 'Access Control Rules' in output
    assert '=' * 70 in output
    assert 'Deny-by-default' in output

    # Check all defined namespaces appear
    for namespace, rule in ACCESS_RULES.items():
        assert namespace in output
        assert rule['description'] in output


def test_list_rules_shows_public_namespace():
    """List rules correctly marks public namespaces."""
    output = list_rules()
    assert 'general.public' in output
    assert 'PUBLIC' in output or 'no competence required' in output


def test_list_rules_shows_competence_requirements():
    """List rules shows required competence scores."""
    output = list_rules()

    # finance.payments requires code: 0.6, security: 0.5
    assert 'finance.payments' in output
    assert 'code: 0.60' in output or 'code: 0.6' in output
    assert 'security: 0.50' in output or 'security: 0.5' in output

    # security.secrets requires security: 0.8
    assert 'security.secrets' in output
    assert 'security: 0.80' in output or 'security: 0.8' in output


def test_access_control_integration_scenario():
    """End-to-end scenario: finance bot accessing payment memories."""
    # Finance bot passport with strong code/security competence
    finance_bot_passport = {
        "credentialSubject": {
            "competence": {
                "code": 0.7,
                "security": 0.6,
                "finance": 0.9
            }
        }
    }

    # Should access finance.payments (code: 0.7 > 0.6, security: 0.6 > 0.5)
    allowed, reason = check_access('finance', 'payments', finance_bot_passport)
    assert allowed is True

    # Should NOT access security.secrets (security: 0.6 < 0.8)
    allowed, reason = check_access('security', 'secrets', finance_bot_passport)
    assert allowed is False

    # Should access code.internal (code: 0.7 > 0.5)
    allowed, reason = check_access('code', 'internal', finance_bot_passport)
    assert allowed is True

    # Test with actual memory filtering
    payment_memories = [
        {'id': 1, 'content': 'PayFast API key', 'wing': 'finance', 'room': 'payments'},
        {'id': 2, 'content': 'Database password', 'wing': 'security', 'room': 'secrets'},
        {'id': 3, 'content': 'Payment flow diagram', 'wing': 'general', 'room': 'public'},
    ]

    filtered = filter_memories_by_access(payment_memories, finance_bot_passport)
    filtered_ids = [m['id'] for m in filtered]

    assert 1 in filtered_ids  # finance.payments (allowed)
    assert 2 not in filtered_ids  # security.secrets (denied)
    assert 3 in filtered_ids  # general.public (public)
