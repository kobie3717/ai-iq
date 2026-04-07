"""
Passport System — A memory's complete identity card.

A passport aggregates a memory's full identity across all dimensions:
- Core content + metadata
- Graph entity connections (what it's linked to)
- Memory relationships (derived-from, related, supersedes)
- Provenance chain (citations, reasoning, derived-from)
- Behavioral profile (how it's been used, access patterns)
- Activation path (spreading activation from this memory's entities)
- Confidence score (composite from multiple signals)

Like a traveler's passport that proves who you are and where you've been,
a memory passport is its complete dossier — everything we know about it.
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from .config import get_logger
from .database import get_db
from .graph import graph_spread

logger = get_logger(__name__)


def calculate_passport_score(
    priority: int,
    access_count: int,
    proof_count: int,
    graph_connections: int,
    days_since_creation: float,
    max_access_count: int = 100
) -> Tuple[float, Dict[str, float]]:
    """
    Calculate a composite passport score from multiple signals.

    Args:
        priority: Memory priority (0-10)
        access_count: Number of times accessed
        proof_count: Number of citations/sources
        graph_connections: Number of entity links
        days_since_creation: Age in days
        max_access_count: Normalization ceiling for access count

    Returns:
        (total_score, breakdown_dict) where total_score is 0-10
    """
    # Normalize priority (already 0-10)
    priority_norm = priority / 10.0

    # Normalize access count (log scale for diminishing returns)
    import math
    access_norm = min(1.0, math.log1p(access_count) / math.log1p(max_access_count))

    # Normalize proof count (log scale)
    proof_norm = min(1.0, math.log1p(proof_count) / math.log1p(10))

    # Normalize graph connections (log scale)
    graph_norm = min(1.0, math.log1p(graph_connections) / math.log1p(20))

    # Recency score (exponential decay, 365 days half-life)
    recency_norm = math.exp(-days_since_creation / 365.0)

    # Weighted combination
    weights = {
        'priority': 0.30,
        'access': 0.20,
        'proof': 0.20,
        'graph': 0.15,
        'recency': 0.15
    }

    scores = {
        'priority': priority_norm * weights['priority'] * 10,
        'access': access_norm * weights['access'] * 10,
        'proof': proof_norm * weights['proof'] * 10,
        'graph': graph_norm * weights['graph'] * 10,
        'recency': recency_norm * weights['recency'] * 10
    }

    total = sum(scores.values())

    return total, scores


def get_passport(memory_id: int) -> Optional[Dict[str, Any]]:
    """
    Generate a complete passport for a memory.

    Returns a structured dict with:
    - core: basic memory data (id, category, content, etc.)
    - metadata: priority, tags, dates, access stats
    - graph: linked entities with their types and 1-hop relationships
    - relations: related memories (derived-from, related, supersedes)
    - provenance: citations, reasoning, derived-from chain
    - stats: access patterns, FSRS state
    - score: passport score breakdown
    - activation: spreading activation results from linked entities
    """
    conn = get_db()

    # 1. Fetch core memory data
    mem = conn.execute("""
        SELECT * FROM memories WHERE id = ? AND active = 1
    """, (memory_id,)).fetchone()

    if not mem:
        conn.close()
        return None

    mem = dict(mem)

    # 2. Get linked graph entities with their details
    entities = conn.execute("""
        SELECT e.id, e.name, e.type, e.summary, e.importance
        FROM memory_entity_links mel
        JOIN graph_entities e ON mel.entity_id = e.id
        WHERE mel.memory_id = ?
        ORDER BY e.importance DESC
    """, (memory_id,)).fetchall()

    entity_data = []
    for ent in entities:
        ent_dict = dict(ent)

        # Get 1-hop relationships for this entity
        rels = conn.execute("""
            SELECT r.relation_type, e2.name as target, e2.type as target_type
            FROM graph_relationships r
            JOIN graph_entities e2 ON r.to_entity_id = e2.id
            WHERE r.from_entity_id = ?
            ORDER BY r.relation_type
        """, (ent['id'],)).fetchall()

        ent_dict['relationships'] = [
            {'type': r['relation_type'], 'target': r['target'], 'target_type': r['target_type']}
            for r in rels
        ]

        entity_data.append(ent_dict)

    # 3. Get memory relationships (both directions)
    relations = conn.execute("""
        SELECT
            CASE
                WHEN source_id = ? THEN 'outgoing'
                ELSE 'incoming'
            END as direction,
            relation_type,
            CASE
                WHEN source_id = ? THEN target_id
                ELSE source_id
            END as other_id
        FROM memory_relations
        WHERE source_id = ? OR target_id = ?
    """, (memory_id, memory_id, memory_id, memory_id)).fetchall()

    relation_data = []
    for rel in relations:
        other_mem = conn.execute("""
            SELECT id, category, content FROM memories WHERE id = ?
        """, (rel['other_id'],)).fetchone()

        if other_mem:
            relation_data.append({
                'direction': rel['direction'],
                'type': rel['relation_type'],
                'memory_id': other_mem['id'],
                'category': other_mem['category'],
                'content_preview': other_mem['content'][:60] + ('...' if len(other_mem['content']) > 60 else '')
            })

    # 4. Parse provenance data
    derived_from_ids = []
    if mem.get('derived_from'):
        try:
            parsed = json.loads(mem['derived_from'])
            # Handle both list and single int
            if isinstance(parsed, list):
                derived_from_ids = parsed
            elif isinstance(parsed, int):
                derived_from_ids = [parsed]
            else:
                derived_from_ids = []
        except (json.JSONDecodeError, TypeError):
            # Try to parse as comma-separated string
            derived_from_ids = [int(x.strip()) for x in str(mem['derived_from']).split(',') if x.strip().isdigit()]

    citations = []
    if mem.get('citations'):
        try:
            citations = json.loads(mem['citations'])
            if isinstance(citations, str):
                citations = [citations]
        except (json.JSONDecodeError, TypeError):
            citations = [str(mem['citations'])]

    # 5. Calculate days since creation
    try:
        created = datetime.fromisoformat(mem['created_at'].replace('Z', '+00:00'))
        days_since = (datetime.now() - created.replace(tzinfo=None)).total_seconds() / 86400
    except (ValueError, AttributeError):
        days_since = 0

    # 6. Get max access count for normalization
    max_access = conn.execute("SELECT MAX(access_count) as m FROM memories").fetchone()['m'] or 100

    # 7. Calculate passport score
    score, breakdown = calculate_passport_score(
        priority=mem.get('priority', 0),
        access_count=mem.get('access_count', 0),
        proof_count=mem.get('proof_count', 1),
        graph_connections=len(entity_data),
        days_since_creation=days_since,
        max_access_count=max(max_access, 100)
    )

    # 8. Spreading activation from linked entities
    activation_results = []
    if entity_data:
        # Take first 3 entities for spreading activation
        for ent in entity_data[:3]:
            try:
                spread = graph_spread(ent['name'], depth=1)
                activation_results.append({
                    'from_entity': ent['name'],
                    'activated': [
                        {'entity': s['name'], 'type': s['type'], 'score': s['score']}
                        for s in spread[:3]  # Top 3 activated entities
                    ]
                })
            except Exception as e:
                logger.debug(f"Spreading activation failed for {ent['name']}: {e}")

    conn.close()

    # Build passport data structure
    passport = {
        'core': {
            'id': mem['id'],
            'category': mem['category'],
            'content': mem['content'],
            'project': mem.get('project'),
        },
        'metadata': {
            'tags': mem.get('tags', '').split(',') if mem.get('tags') else [],
            'priority': mem.get('priority', 0),
            'topic_key': mem.get('topic_key'),
            'source': mem.get('source', 'manual'),
            'confidence': mem.get('confidence', 0.7),
        },
        'dates': {
            'created_at': mem['created_at'],
            'updated_at': mem['updated_at'],
            'accessed_at': mem.get('accessed_at'),
            'expires_at': mem.get('expires_at'),
            'days_since_creation': round(days_since, 1),
        },
        'stats': {
            'access_count': mem.get('access_count', 0),
            'revision_count': mem.get('revision_count', 1),
            'stale': bool(mem.get('stale', 0)),
        },
        'fsrs': {
            'stability': mem.get('fsrs_stability', 1.0),
            'difficulty': mem.get('fsrs_difficulty', 5.0),
            'interval': mem.get('fsrs_interval', 1.0),
            'reps': mem.get('fsrs_reps', 0),
        },
        'graph': entity_data,
        'relations': relation_data,
        'provenance': {
            'derived_from': derived_from_ids,
            'citations': citations,
            'reasoning': mem.get('reasoning'),
            'proof_count': mem.get('proof_count', 1),
        },
        'score': {
            'total': round(score, 2),
            'breakdown': {k: round(v, 2) for k, v in breakdown.items()},
        },
        'activation': activation_results,
    }

    return passport


def display_passport(passport: Dict[str, Any]) -> None:
    """Pretty-print a passport."""
    if not passport:
        print("Memory not found or inactive.")
        return

    core = passport['core']
    meta = passport['metadata']
    dates = passport['dates']
    stats = passport['stats']
    graph = passport['graph']
    relations = passport['relations']
    prov = passport['provenance']
    score = passport['score']
    activation = passport['activation']

    # Header
    print(f"\n🪪 PASSPORT — Memory #{core['id']}")
    print("=" * 70)

    # Core identity
    print(f"\n📌 CORE IDENTITY")
    print(f"  Category: {core['category']}")
    if core['project']:
        print(f"  Project: {core['project']}")
    print(f"  Content: {core['content']}")

    # Metadata
    print(f"\n🏷️  METADATA")
    if meta['tags']:
        print(f"  Tags: {', '.join(meta['tags'])}")
    print(f"  Priority: {meta['priority']}/10")
    if meta['topic_key']:
        print(f"  Topic Key: {meta['topic_key']}")
    print(f"  Source: {meta['source']}")
    print(f"  Confidence: {meta['confidence']:.2f}")

    # Timeline
    print(f"\n📅 TIMELINE")
    print(f"  Created: {dates['created_at']}")
    if dates['accessed_at']:
        print(f"  Last Accessed: {dates['accessed_at']}")
    print(f"  Age: {dates['days_since_creation']} days")
    if dates['expires_at']:
        print(f"  Expires: {dates['expires_at']}")

    # Usage stats
    print(f"\n📊 USAGE STATS")
    print(f"  Accessed: {stats['access_count']} times")
    print(f"  Revisions: {stats['revision_count']}")
    if stats['stale']:
        print(f"  ⚠️  Flagged as stale")

    # Graph connections
    if graph:
        print(f"\n🕸️  GRAPH CONNECTIONS ({len(graph)} entities)")
        for ent in graph:
            print(f"  • {ent['name']} ({ent['type']}) — importance: {ent['importance']}/10")
            if ent.get('summary'):
                print(f"    {ent['summary']}")
            if ent.get('relationships'):
                for rel in ent['relationships'][:3]:  # Show first 3
                    print(f"    → {rel['type']} → {rel['target']} ({rel['target_type']})")
    else:
        print(f"\n🕸️  GRAPH CONNECTIONS: None")

    # Memory relationships
    if relations:
        print(f"\n🔗 MEMORY RELATIONSHIPS ({len(relations)})")
        for rel in relations:
            arrow = "→" if rel['direction'] == 'outgoing' else "←"
            print(f"  {arrow} {rel['type']} #{rel['memory_id']} [{rel['category']}]")
            print(f"    {rel['content_preview']}")
    else:
        print(f"\n🔗 MEMORY RELATIONSHIPS: None")

    # Provenance
    print(f"\n📜 PROVENANCE")
    if prov['derived_from']:
        print(f"  Derived from: {', '.join(f'#{m}' for m in prov['derived_from'])}")
    if prov['citations']:
        print(f"  Citations ({len(prov['citations'])}):")
        for cite in prov['citations']:
            print(f"    • {cite}")
    if prov['reasoning']:
        print(f"  Reasoning: {prov['reasoning']}")
    print(f"  Proof count: {prov['proof_count']}")

    # Passport score
    print(f"\n⭐ PASSPORT SCORE: {score['total']:.2f} / 10.00")
    print(f"  Breakdown:")
    for component, value in score['breakdown'].items():
        print(f"    {component.capitalize()}: {value:.2f}")

    # Spreading activation
    if activation:
        print(f"\n🌊 SPREADING ACTIVATION")
        for act in activation:
            print(f"  From {act['from_entity']}:")
            if act['activated']:
                for node in act['activated']:
                    print(f"    • {node['entity']} ({node['type']}) — score: {node['score']:.3f}")
            else:
                print(f"    (no connections)")

    print("\n" + "=" * 70)
