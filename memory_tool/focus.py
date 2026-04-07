"""Focus command - instant context brief on any topic."""

import sqlite3
from typing import List, Dict, Any, Optional
from .database import get_db
from .memory_ops import search_memories
from .graph import graph_get_entity, graph_spread
from .display import format_row_compact
from .config import get_logger

logger = get_logger(__name__)


def focus_topic(topic: str, full: bool = False) -> str:
    """Generate a context brief for a topic by pulling all relevant data.

    Args:
        topic: The topic to focus on
        full: If True, show more detailed output

    Returns:
        Markdown-formatted context brief
    """
    conn = get_db()
    output = []

    # Header
    output.append(f"# Focus: {topic}\n")

    # ── 1. Search Memories ──
    try:
        rows, search_id, temporal_range = search_memories(topic, mode="hybrid")

        if rows:
            # Limit to top 10 for focus view, top 5 for compact
            limit = 10 if full else 5
            top_rows = rows[:limit]

            output.append(f"## Key Memories ({len(top_rows)} of {len(rows)} matches)\n")
            for r in top_rows:
                if full:
                    # Full format
                    tags = f" tags:{r['tags']}" if r["tags"] else ""
                    proj = f" [{r['project']}]" if r["project"] else ""
                    cat = r['category']
                    date = r['updated_at'][:10]
                    content = r['content']
                    output.append(f"- **#{r['id']}** {proj} ({cat}, {date}){tags}")
                    output.append(f"  {content}\n")
                else:
                    # Compact format
                    proj = f"[{r['project']}] " if r["project"] else ""
                    cat = r['category']
                    date = r['updated_at'][:10]
                    content_preview = r['content'][:80]
                    if len(r['content']) > 80:
                        content_preview += "..."
                    output.append(f"- **#{r['id']}** {proj}{content_preview} ({cat}, {date})")

            output.append("")  # blank line
        else:
            output.append("## Key Memories\n_No memories found._\n")
    except Exception as e:
        logger.error(f"Error searching memories: {e}")
        output.append("## Key Memories\n_Error retrieving memories._\n")

    # ── 2. Knowledge Graph ──
    try:
        entity_data = graph_get_entity(topic)

        if entity_data:
            entity = entity_data['entity']
            facts = entity_data['facts']
            relationships = entity_data['outgoing'] + entity_data['incoming']
            memories = entity_data['memories']

            output.append("## Knowledge Graph\n")
            output.append(f"**Entity:** {entity['name']} ({entity['type']})\n")

            # Facts
            if facts:
                output.append("**Facts:**")
                for fact in facts[:10 if full else 5]:
                    conf_str = f" (confidence: {fact['confidence']:.2f})" if fact.get('confidence') and fact['confidence'] < 1.0 else ""
                    output.append(f"- {fact['key']}: {fact['value']}{conf_str}")
                output.append("")

            # Relationships
            if relationships:
                output.append("**Relationships:**")
                for rel in relationships[:15 if full else 10]:
                    # Handle both outgoing and incoming
                    if 'to_name' in rel:
                        output.append(f"- → **{rel['to_name']}** ({rel['relation_type']})")
                    elif 'from_name' in rel:
                        output.append(f"- ← **{rel['from_name']}** ({rel['relation_type']})")
                output.append("")

            # Linked memories
            if memories:
                mem_count = len(memories)
                output.append(f"**Linked Memories:** {mem_count} total")
                if full:
                    for mem in memories[:5]:
                        output.append(f"- #{mem['id']}: {mem['content'][:60]}...")
                output.append("")

            # Related entities via spreading activation
            if not full:
                try:
                    related_entities = graph_spread(topic, depth=1)
                    if related_entities and len(related_entities) > 1:  # More than just the topic itself
                        output.append("**Related Entities:**")
                        for ent in related_entities[1:6]:  # Skip first (the topic itself), show next 5
                            output.append(f"- {ent['name']} (score: {ent['score']:.2f})")
                        output.append("")
                except Exception as e:
                    logger.debug(f"Could not get related entities: {e}")
        else:
            output.append("## Knowledge Graph\n_No entity found for this topic._\n")
    except Exception as e:
        logger.error(f"Error retrieving graph entity: {e}")
        output.append("## Knowledge Graph\n_Error retrieving entity._\n")

    # ── 3. Last Session ──
    try:
        # Find latest snapshot mentioning this topic
        snapshot_row = conn.execute("""
            SELECT id, summary, created_at, project
            FROM session_snapshots
            WHERE LOWER(summary) LIKE LOWER(?)
            ORDER BY created_at DESC
            LIMIT 1
        """, (f"%{topic}%",)).fetchone()

        if snapshot_row:
            output.append("## Last Session\n")
            date = snapshot_row['created_at'][:10]
            proj = f"[{snapshot_row['project']}] " if snapshot_row['project'] else ""
            # Truncate summary to ~200 chars
            summary = snapshot_row['summary']
            if len(summary) > 200:
                summary = summary[:197] + "..."
            output.append(f"{proj}{summary} _{date}_\n")
    except Exception as e:
        logger.debug(f"Error retrieving last session: {e}")

    # ── 4. Active Runs ──
    try:
        # Find in-progress runs matching topic
        active_runs = conn.execute("""
            SELECT id, task, agent, started_at, steps, project
            FROM runs
            WHERE status IN ('running', 'active')
            AND (LOWER(task) LIKE LOWER(?) OR LOWER(project) LIKE LOWER(?))
            ORDER BY started_at DESC
            LIMIT 5
        """, (f"%{topic}%", f"%{topic}%")).fetchall()

        if active_runs:
            output.append(f"## Active Runs ({len(active_runs)} in progress)\n")
            for run in active_runs:
                import json
                try:
                    steps = json.loads(run['steps']) if run['steps'] else []
                    step_count = len(steps)
                except (json.JSONDecodeError, TypeError):
                    step_count = 0

                proj = f"[{run['project']}] " if run['project'] else ""
                task_preview = run['task'][:60]
                if len(run['task']) > 60:
                    task_preview += "..."
                agent_info = f" ({run['agent']})" if run['agent'] != 'claw' else ""
                output.append(f"- **#{run['id']}** {proj}{task_preview}{agent_info} - {step_count} steps")
            output.append("")
    except Exception as e:
        logger.debug(f"Error retrieving active runs: {e}")

    # ── 5. Pending Items ──
    try:
        # Search pending category for mentions of topic
        pending_rows = conn.execute("""
            SELECT id, content, updated_at, project
            FROM memories
            WHERE active = 1 AND category = 'pending'
            AND (LOWER(content) LIKE LOWER(?) OR LOWER(project) LIKE LOWER(?))
            ORDER BY updated_at DESC
            LIMIT 10
        """, (f"%{topic}%", f"%{topic}%")).fetchall()

        if pending_rows:
            output.append(f"## Pending ({len(pending_rows)} items)\n")
            for row in pending_rows:
                proj = f"[{row['project']}] " if row['project'] else ""
                content_preview = row['content'][:60]
                if len(row['content']) > 60:
                    content_preview += "..."
                output.append(f"- **#{row['id']}** {proj}{content_preview}")
            output.append("")
    except Exception as e:
        logger.debug(f"Error retrieving pending items: {e}")

    # ── 6. Beliefs ──
    try:
        beliefs = conn.execute("""
            SELECT id, statement, confidence, category, updated_at
            FROM beliefs
            WHERE LOWER(statement) LIKE LOWER(?)
            ORDER BY confidence DESC
            LIMIT 10
        """, (f"%{topic}%",)).fetchall()

        if beliefs:
            output.append(f"## Beliefs ({len(beliefs)} found)\n")
            for b in beliefs:
                cat = f"[{b['category']}] " if b['category'] else ""
                stmt_preview = b['statement'][:70]
                if len(b['statement']) > 70:
                    stmt_preview += "..."
                output.append(f"- **#{b['id']}** {cat}{stmt_preview} (confidence: {b['confidence']:.2f})")
            output.append("")
    except Exception as e:
        logger.debug(f"Error retrieving beliefs: {e}")

    # ── 7. Predictions ──
    try:
        predictions = conn.execute("""
            SELECT id, prediction, confidence, status, deadline, updated_at
            FROM predictions
            WHERE LOWER(prediction) LIKE LOWER(?)
            AND status IN ('open', 'pending')
            ORDER BY deadline ASC
            LIMIT 10
        """, (f"%{topic}%",)).fetchall()

        if predictions:
            output.append(f"## Predictions ({len(predictions)} open)\n")
            for p in predictions:
                pred_preview = p['prediction'][:70]
                if len(p['prediction']) > 70:
                    pred_preview += "..."
                deadline_str = f" (deadline: {p['deadline'][:10]})" if p['deadline'] else ""
                output.append(f"- **#{p['id']}** {pred_preview} (confidence: {p['confidence']:.2f}){deadline_str}")
            output.append("")
    except Exception as e:
        logger.debug(f"Error retrieving predictions: {e}")

    # ── 8. Suggested Actions ──
    suggestions = []

    # Check for stale memories related to topic
    try:
        stale_count = conn.execute("""
            SELECT COUNT(*) as c FROM memories
            WHERE active = 1 AND stale = 1
            AND (LOWER(content) LIKE LOWER(?) OR LOWER(project) LIKE LOWER(?))
        """, (f"%{topic}%", f"%{topic}%")).fetchone()["c"]

        if stale_count:
            suggestions.append(f"- Review {stale_count} stale memories: `memory-tool search \"{topic}\" | grep STALE`")
    except Exception:
        pass

    # Check for expired predictions
    try:
        expired_pred = conn.execute("""
            SELECT COUNT(*) as c FROM predictions
            WHERE LOWER(prediction) LIKE LOWER(?)
            AND status = 'open'
            AND deadline IS NOT NULL
            AND deadline < datetime('now')
        """, (f"%{topic}%",)).fetchone()["c"]

        if expired_pred:
            suggestions.append(f"- Resolve {expired_pred} expired predictions: `memory-tool predictions --expired`")
    except Exception:
        pass

    # Check for conflicts
    try:
        # Simple conflict check: look for high-similarity pairs mentioning this topic
        conflict_rows = conn.execute("""
            SELECT COUNT(*) as c FROM memories
            WHERE active = 1
            AND (LOWER(content) LIKE LOWER(?) OR LOWER(project) LIKE LOWER(?))
        """, (f"%{topic}%", f"%{topic}%")).fetchone()["c"]

        if conflict_rows >= 5:
            suggestions.append(f"- Check for conflicts: `memory-tool conflicts` (found {conflict_rows} memories)")
    except Exception:
        pass

    if suggestions:
        output.append("## Suggested Actions\n")
        output.extend(suggestions)
        output.append("")

    conn.close()

    # Return formatted markdown
    return "\n".join(output)


def cmd_focus(topic: str, full: bool = False) -> None:
    """Command-line wrapper for focus_topic."""
    result = focus_topic(topic, full)
    print(result)
