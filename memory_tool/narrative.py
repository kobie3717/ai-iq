"""Narrative Memory — builds cause-effect stories from the knowledge graph.

Walks causal graph edges (LEADS_TO, PREVENTS, RESOLVES, REQUIRES) and
linked memories to construct chronological narratives about entities.
"""

import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from .database import get_db
from .config import get_logger

logger = get_logger(__name__)


def build_narrative(db: sqlite3.Connection, entity_name: str, max_depth: int = 3) -> Dict[str, Any]:
    """Build a cause-effect narrative for an entity.

    Walks the graph starting from the named entity, following causal edges
    and collecting linked memories to construct a chronological story.

    Args:
        db: Database connection
        entity_name: Name of the entity to build narrative for
        max_depth: How deep to traverse relationships (default 3)

    Returns:
        Dict with 'entity', 'events' (chronological), 'narrative' (text), 'connections'
    """
    # Find the entity
    entity = db.execute(
        "SELECT * FROM graph_entities WHERE LOWER(name) = LOWER(?)",
        (entity_name,)
    ).fetchone()

    if not entity:
        return {'entity': None, 'events': [], 'narrative': '', 'connections': 0}

    entity_id = entity['id']
    entity_dict = dict(entity)

    # Collect all connected entities via causal edges
    visited = set()
    events = []

    _collect_narrative_events(db, entity_id, visited, events, max_depth, 0)

    # Also get directly linked memories
    linked_memories = db.execute("""
        SELECT m.id, m.content, m.category, m.project, m.created_at, m.confidence
        FROM memories m
        JOIN memory_entity_links mel ON m.id = mel.memory_id
        WHERE mel.entity_id = ? AND m.active = 1
        ORDER BY m.created_at ASC
    """, (entity_id,)).fetchall()

    for mem in linked_memories:
        events.append({
            'type': 'memory',
            'id': mem['id'],
            'content': mem['content'],
            'category': mem['category'],
            'project': mem['project'],
            'date': mem['created_at'],
            'confidence': mem['confidence'] or 0.7,
            'source_entity': entity_name,
            'relation': 'linked'
        })

    # Sort by date
    events.sort(key=lambda e: e.get('date', '9999'))

    # Deduplicate by content similarity
    events = _deduplicate_events(events)

    # Generate narrative text
    narrative = _generate_narrative_text(entity_name, events)

    return {
        'entity': entity_dict,
        'events': events,
        'narrative': narrative,
        'connections': len(events)
    }


def _collect_narrative_events(
    db: sqlite3.Connection,
    entity_id: int,
    visited: set,
    events: list,
    max_depth: int,
    current_depth: int
) -> None:
    """Recursively collect events by walking causal graph edges."""
    if entity_id in visited or current_depth > max_depth:
        return

    visited.add(entity_id)

    # Get entity info
    entity = db.execute(
        "SELECT name, type FROM graph_entities WHERE id = ?", (entity_id,)
    ).fetchone()
    if not entity:
        return

    entity_name = entity['name']

    # Get causal relationships (outgoing)
    causal_types = ('leads_to', 'prevents', 'resolves', 'requires', 'depends_on', 'uses', 'built_by')
    placeholders = ','.join('?' * len(causal_types))

    outgoing = db.execute(f"""
        SELECT gr.relation_type, gr.note, gr.created_at,
               ge.id as target_id, ge.name as target_name, ge.type as target_type
        FROM graph_relationships gr
        JOIN graph_entities ge ON gr.to_entity_id = ge.id
        WHERE gr.from_entity_id = ?
        AND LOWER(gr.relation_type) IN ({placeholders})
    """, (entity_id, *causal_types)).fetchall()

    for rel in outgoing:
        events.append({
            'type': 'relationship',
            'source_entity': entity_name,
            'target_entity': rel['target_name'],
            'relation': rel['relation_type'],
            'note': rel['note'] or '',
            'date': rel['created_at'],
            'content': f"{entity_name} {_relation_verb(rel['relation_type'])} {rel['target_name']}"
                       + (f" ({rel['note']})" if rel['note'] else ''),
            'confidence': 1.0
        })

        # Recurse into target entity
        _collect_narrative_events(db, rel['target_id'], visited, events, max_depth, current_depth + 1)

    # Get incoming relationships too
    incoming = db.execute(f"""
        SELECT gr.relation_type, gr.note, gr.created_at,
               ge.id as source_id, ge.name as source_name, ge.type as source_type
        FROM graph_relationships gr
        JOIN graph_entities ge ON gr.from_entity_id = ge.id
        WHERE gr.to_entity_id = ?
        AND LOWER(gr.relation_type) IN ({placeholders})
    """, (entity_id, *causal_types)).fetchall()

    for rel in incoming:
        events.append({
            'type': 'relationship',
            'source_entity': rel['source_name'],
            'target_entity': entity_name,
            'relation': rel['relation_type'],
            'note': rel['note'] or '',
            'date': rel['created_at'],
            'content': f"{rel['source_name']} {_relation_verb(rel['relation_type'])} {entity_name}"
                       + (f" ({rel['note']})" if rel['note'] else ''),
            'confidence': 1.0
        })

        _collect_narrative_events(db, rel['source_id'], visited, events, max_depth, current_depth + 1)

    # Get linked memories for this entity
    memories = db.execute("""
        SELECT m.id, m.content, m.category, m.project, m.created_at, m.confidence
        FROM memories m
        JOIN memory_entity_links mel ON m.id = mel.memory_id
        WHERE mel.entity_id = ? AND m.active = 1
        ORDER BY m.created_at ASC
    """, (entity_id,)).fetchall()

    for mem in memories:
        events.append({
            'type': 'memory',
            'id': mem['id'],
            'content': mem['content'],
            'category': mem['category'],
            'project': mem['project'],
            'date': mem['created_at'],
            'confidence': mem['confidence'] or 0.7,
            'source_entity': entity_name,
            'relation': 'linked'
        })


def _relation_verb(relation_type: str) -> str:
    """Convert relation type to a human-readable verb."""
    verbs = {
        'leads_to': '→ led to',
        'prevents': '⊘ prevents',
        'resolves': '✓ resolved',
        'requires': '⚡ requires',
        'depends_on': '← depends on',
        'uses': '⚙ uses',
        'built_by': '🔨 built by',
        'blocks': '⊘ blocks',
        'related_to': '~ relates to',
        'knows': '👤 knows',
        'works_on': '💼 works on',
        'owns': '🏠 owns',
    }
    return verbs.get(relation_type.lower(), f'-- {relation_type} -->')


def _deduplicate_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove near-duplicate events based on content similarity."""
    if not events:
        return events

    seen_content = set()
    unique = []

    for event in events:
        # Simple dedup key: first 80 chars of content
        key = event.get('content', '')[:80].lower().strip()
        if key not in seen_content:
            seen_content.add(key)
            unique.append(event)

    return unique


def _generate_narrative_text(entity_name: str, events: List[Dict[str, Any]]) -> str:
    """Generate a readable narrative from chronological events."""
    if not events:
        return f"No narrative found for '{entity_name}'."

    lines = [f"Story of {entity_name}:", ""]

    current_date = None

    for event in events:
        # Group by date (day level)
        event_date = event.get('date', '')[:10] if event.get('date') else 'Unknown'
        if event_date != current_date:
            current_date = event_date
            lines.append(f"[{current_date}]")

        # Format based on type
        if event['type'] == 'relationship':
            lines.append(f"  {event['content']}")
        elif event['type'] == 'memory':
            conf_str = f" ({event['confidence']:.0%})" if event.get('confidence') else ""
            cat = f"[{event.get('category', '?')}]"
            content = event['content'][:120]
            lines.append(f"  {cat} {content}{conf_str}")

    lines.append("")
    lines.append(f"--- {len(events)} events traced ---")

    return "\n".join(lines)


def get_entity_stories(db: sqlite3.Connection, limit: int = 10) -> List[Dict[str, Any]]:
    """Get entities with the richest narratives (most connections + memories).

    Args:
        db: Database connection
        limit: Max entities to return

    Returns:
        List of dicts with entity info and connection counts
    """
    rows = db.execute("""
        SELECT ge.name, ge.type, ge.summary,
               COUNT(DISTINCT gr_out.id) + COUNT(DISTINCT gr_in.id) as rel_count,
               COUNT(DISTINCT mel.memory_id) as mem_count
        FROM graph_entities ge
        LEFT JOIN graph_relationships gr_out ON ge.id = gr_out.from_entity_id
        LEFT JOIN graph_relationships gr_in ON ge.id = gr_in.to_entity_id
        LEFT JOIN memory_entity_links mel ON ge.id = mel.entity_id
        GROUP BY ge.id
        HAVING rel_count + mem_count > 0
        ORDER BY rel_count + mem_count DESC
        LIMIT ?
    """, (limit,)).fetchall()

    return [dict(r) for r in rows]


def get_causal_chains(db: sqlite3.Connection, entity_name: str) -> List[List[str]]:
    """Find all causal chains starting from or passing through an entity.

    Returns a list of chains, each chain being a list of entity names
    connected by causal relationships.

    Args:
        db: Database connection
        entity_name: Starting entity name

    Returns:
        List of chains (each chain is a list of entity name strings)
    """
    entity = db.execute(
        "SELECT id FROM graph_entities WHERE LOWER(name) = LOWER(?)",
        (entity_name,)
    ).fetchone()

    if not entity:
        return []

    chains = []
    _find_chains(db, entity['id'], [entity_name], set(), chains, max_depth=5)

    return chains


def _find_chains(
    db: sqlite3.Connection,
    entity_id: int,
    current_chain: List[str],
    visited: set,
    chains: List[List[str]],
    max_depth: int
) -> None:
    """Recursively find causal chains."""
    if len(current_chain) > max_depth:
        if len(current_chain) > 1:
            chains.append(list(current_chain))
        return

    visited.add(entity_id)

    # Follow leads_to and resolves edges forward
    nexts = db.execute("""
        SELECT ge.id, ge.name
        FROM graph_relationships gr
        JOIN graph_entities ge ON gr.to_entity_id = ge.id
        WHERE gr.from_entity_id = ?
        AND LOWER(gr.relation_type) IN ('leads_to', 'resolves', 'requires')
    """, (entity_id,)).fetchall()

    if not nexts:
        # End of chain
        if len(current_chain) > 1:
            chains.append(list(current_chain))
        return

    for n in nexts:
        if n['id'] not in visited:
            current_chain.append(n['name'])
            _find_chains(db, n['id'], current_chain, visited, chains, max_depth)
            current_chain.pop()

    visited.discard(entity_id)

    # Also save current chain if it has length
    if len(current_chain) > 1 and current_chain not in chains:
        chains.append(list(current_chain))
