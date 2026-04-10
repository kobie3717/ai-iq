"""
Integration tests for access control in search flow.

Tests that passport credentials properly filter memories by wing/room namespaces.
"""

import pytest
import tempfile
import os
from memory_tool.database import init_db, get_db
from memory_tool.memory_ops import add_memory, search_memories
from memory_tool.access_control import check_access, filter_memories_by_access


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Set DB path for this test
    original_path = os.environ.get('MEMORY_DB')
    os.environ['MEMORY_DB'] = db_path

    # Initialize schema
    init_db()

    yield db_path

    # Cleanup
    if original_path:
        os.environ['MEMORY_DB'] = original_path
    else:
        del os.environ['MEMORY_DB']
    os.unlink(db_path)


def test_search_without_passport_shows_all(test_db):
    """Search without passport should return all memories (backward compat)."""
    # Add memories with unique marker (skip_dedup to avoid blocking)
    add_memory("learning", "TEST_A marker abc999", wing="general", room="public", skip_dedup=True)
    add_memory("learning", "TEST_B marker abc999", wing="finance", room="payments", skip_dedup=True)
    add_memory("learning", "TEST_C marker abc999", wing="security", room="secrets", skip_dedup=True)

    # Search without passport
    rows, _, _ = search_memories("abc999", mode="keyword")

    # Should see all 3 test memories
    contents = [r['content'] for r in rows]
    assert any('TEST_A' in c for c in contents), "Should see public memory"
    assert any('TEST_B' in c for c in contents), "Should see payment memory"
    assert any('TEST_C' in c for c in contents), "Should see secret memory"


def test_search_with_low_competence_filters_restricted(test_db):
    """Low-competence passport should filter out restricted memories."""
    # Add memories with unique markers (skip_dedup to avoid blocking)
    add_memory("learning", "TEST_PUBLIC knowledge xyz123", wing="general", room="public", skip_dedup=True)
    add_memory("learning", "TEST_PAYMENT processing logic xyz123", wing="finance", room="payments", skip_dedup=True)
    add_memory("learning", "TEST_SECRET keys xyz123", wing="security", room="secrets", skip_dedup=True)

    # Low-competence passport (code: 0.3, security: 0.2)
    # Should NOT have access to finance.payments (needs code: 0.6) or security.secrets (needs security: 0.8)
    low_passport = {
        'credentialSubject': {
            'competence': {
                'code': 0.3,
                'security': 0.2
            }
        }
    }

    # Search for our specific test memories with low passport
    rows, _, _ = search_memories("xyz123", mode="keyword", passport_credential=low_passport)

    # Should only see TEST_PUBLIC (not TEST_PAYMENT or TEST_SECRET)
    contents = [r['content'] for r in rows]
    assert any('TEST_PUBLIC' in c for c in contents), "Should see public memory"
    assert not any('TEST_PAYMENT' in c for c in contents), "Should NOT see payment memory (insufficient code competence)"
    assert not any('TEST_SECRET' in c for c in contents), "Should NOT see secret memory (insufficient security competence)"


def test_search_with_high_competence_shows_more(test_db):
    """High-competence passport should allow access to more memories."""
    # Add memories with unique marker (skip_dedup to avoid blocking)
    add_memory("learning", "HIGH_A marker def777", wing="general", room="public", skip_dedup=True)
    add_memory("learning", "HIGH_B marker def777", wing="finance", room="payments", skip_dedup=True)
    add_memory("learning", "HIGH_C marker def777", wing="code", room="internal", skip_dedup=True)
    add_memory("learning", "HIGH_D marker def777", wing="devops", room="production", skip_dedup=True)

    # High-competence passport
    # Should have access to finance.payments, code.internal, devops.production
    high_passport = {
        'credentialSubject': {
            'competence': {
                'code': 0.9,
                'security': 0.7,
                'devops': 0.8
            }
        }
    }

    # Search with high passport
    rows, _, _ = search_memories("def777", mode="keyword", passport_credential=high_passport)

    # Should see all 4 test memories
    contents = [r['content'] for r in rows]
    assert any('HIGH_A' in c for c in contents), "Should see public"
    assert any('HIGH_B' in c for c in contents), "Should see payments"
    assert any('HIGH_C' in c for c in contents), "Should see internal code"
    assert any('HIGH_D' in c for c in contents), "Should see production"


def test_search_with_partial_competence(test_db):
    """Passport with partial competence should get partial access."""
    # Add memories with unique marker (skip_dedup to avoid blocking)
    add_memory("learning", "PART_A marker ghi555", wing="general", room="public", skip_dedup=True)
    add_memory("learning", "PART_B marker ghi555", wing="finance", room="payments", skip_dedup=True)  # needs code:0.6, security:0.5
    add_memory("learning", "PART_C marker ghi555", wing="security", room="secrets", skip_dedup=True)  # needs security:0.8

    # Passport with code competence but low security
    partial_passport = {
        'credentialSubject': {
            'competence': {
                'code': 0.7,      # Meets finance.payments requirement (0.6)
                'security': 0.5   # Meets finance.payments requirement (0.5), but NOT secrets (0.8)
            }
        }
    }

    # Search with partial passport
    rows, _, _ = search_memories("ghi555", mode="keyword", passport_credential=partial_passport)

    # Should see general.public + finance.payments but NOT secrets
    contents = [r['content'] for r in rows]
    assert any('PART_A' in c for c in contents), "Should see public"
    assert any('PART_B' in c for c in contents), "Should see payments (has sufficient competence)"
    assert not any('PART_C' in c for c in contents), "Should NOT see secrets (insufficient security competence)"


def test_search_undefined_namespace_denied(test_db):
    """Undefined namespaces should be denied (deny-by-default)."""
    # Add memory with undefined namespace and unique marker
    add_memory("learning", "UNDEF_A marker jkl333", wing="experimental", room="alpha")

    # Even high-competence passport can't access undefined namespace
    high_passport = {
        'credentialSubject': {
            'competence': {
                'code': 1.0,
                'security': 1.0,
                'devops': 1.0
            }
        }
    }

    # Search with high passport for our specific test memory
    rows, _, _ = search_memories("jkl333", mode="keyword", passport_credential=high_passport)

    # Should NOT see UNDEF_A (undefined namespace blocked)
    contents = [r['content'] for r in rows]
    assert not any('UNDEF_A' in c for c in contents), "Should NOT see undefined namespace even with high competence"


def test_search_no_namespace_always_accessible(test_db):
    """Memories without wing/room should always be accessible."""
    # Add memories without namespaces with unique marker (skip_dedup to avoid blocking)
    add_memory("learning", "NONS_A marker mno111", skip_dedup=True)
    add_memory("learning", "NONS_B marker mno111", skip_dedup=True)

    # Even empty passport should see these
    empty_passport = {
        'credentialSubject': {
            'competence': {}
        }
    }

    # Search with empty passport
    rows, _, _ = search_memories("mno111", mode="keyword", passport_credential=empty_passport)

    # Should see both memories (no namespace = general access)
    contents = [r['content'] for r in rows]
    assert any('NONS_A' in c for c in contents), "Should see first no-namespace memory"
    assert any('NONS_B' in c for c in contents), "Should see second no-namespace memory"


def test_filter_memories_by_access_direct():
    """Test filter_memories_by_access function directly."""
    # Mock memory rows
    rows = [
        {'id': 1, 'wing': 'general', 'room': 'public', 'content': 'Public'},
        {'id': 2, 'wing': 'finance', 'room': 'payments', 'content': 'Payment code'},
        {'id': 3, 'wing': 'security', 'room': 'secrets', 'content': 'Secrets'},
        {'id': 4, 'wing': None, 'room': None, 'content': 'No namespace'},
    ]

    # Low-competence passport
    low_passport = {
        'credentialSubject': {
            'competence': {
                'code': 0.3,
                'security': 0.2
            }
        }
    }

    # Filter
    filtered = filter_memories_by_access(rows, low_passport)

    # Should only have general.public and no-namespace
    assert len(filtered) == 2
    ids = {r['id'] for r in filtered}
    assert 1 in ids  # general.public
    assert 4 in ids  # no namespace
    assert 2 not in ids  # finance.payments blocked
    assert 3 not in ids  # security.secrets blocked


def test_check_access_logic():
    """Test check_access function directly."""
    # Test public namespace
    allowed, reason = check_access('general', 'public', None)
    assert allowed is True

    # Test restricted namespace without passport
    allowed, reason = check_access('finance', 'payments', None)
    assert allowed is False
    assert 'Authentication required' in reason

    # Test undefined namespace
    allowed, reason = check_access('undefined', 'namespace', {'credentialSubject': {'competence': {}}})
    assert allowed is False
    assert 'Undefined namespace' in reason

    # Test sufficient competence
    passport = {
        'credentialSubject': {
            'competence': {
                'code': 0.7,
                'security': 0.6
            }
        }
    }
    allowed, reason = check_access('finance', 'payments', passport)
    assert allowed is True

    # Test insufficient competence
    low_passport = {
        'credentialSubject': {
            'competence': {
                'code': 0.3,
                'security': 0.2
            }
        }
    }
    allowed, reason = check_access('finance', 'payments', low_passport)
    assert allowed is False
    assert 'Insufficient competence' in reason
