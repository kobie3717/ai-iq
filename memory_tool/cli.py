"""Command-line interface for memory-tool."""

import sys
import json
import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any

# Import all operations from the core module (which re-exports everything)
from . import core
from .core import *
from .config import get_logger, setup_logging

logger = get_logger(__name__)


def parse_flags(argv: List[str], start: int = 2) -> Tuple[Dict[str, Any], List[str]]:
    """Parse --flag value pairs from argv starting at position `start`.
    Returns (flags_dict, remaining_args).
    """
    flags = {}
    remaining = []
    i = start
    while i < len(argv):
        arg = argv[i]
        if arg.startswith("--"):
            key = arg[2:]
            if i + 1 < len(argv) and not argv[i+1].startswith("--"):
                flags[key] = argv[i+1]
                i += 2
            else:
                flags[key] = True
                i += 1
        else:
            remaining.append(arg)
            i += 1
    return flags, remaining

def main() -> None:
    init_db()

    # Handle global flags for logging
    if '--verbose' in sys.argv or '-v' in sys.argv:
        logging.getLogger().setLevel(logging.DEBUG)
        if '--verbose' in sys.argv:
            sys.argv.remove('--verbose')
        if '-v' in sys.argv:
            sys.argv.remove('-v')
    elif '--quiet' in sys.argv or '-q' in sys.argv:
        logging.getLogger().setLevel(logging.WARNING)
        if '--quiet' in sys.argv:
            sys.argv.remove('--quiet')
        if '-q' in sys.argv:
            sys.argv.remove('-q')

    if len(sys.argv) < 2:
        print_help()
        sys.exit(0)

    # Parse global flags for verbose/quiet BEFORE command processing
    cmd = sys.argv[1]

    # Check for --verbose or --quiet flags anywhere in argv
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    quiet = '--quiet' in sys.argv or '-q' in sys.argv
    setup_logging(verbose=verbose, quiet=quiet)

    if cmd == "add" and len(sys.argv) >= 4:
        category = sys.argv[2]
        content = sys.argv[3]
        flags, _ = parse_flags(sys.argv, 4)
        add_memory(
            category, content,
            tags=flags.get("tags", ""),
            project=flags.get("project"),
            priority=int(flags.get("priority", 0)),
            related_to=flags.get("related"),
            expires_at=flags.get("expires"),
            source=flags.get("source", "manual"),
            topic_key=flags.get("key"),
            derived_from=flags.get("derived-from"),
            citations=flags.get("citations"),
            reasoning=flags.get("reasoning"),
        )

    elif cmd == "search" and len(sys.argv) >= 3:
        from .modes import get_mode_config
        from .display import show_token_economics, estimate_tokens

        flags, query_parts = parse_flags(sys.argv, 2)
        query = " ".join(query_parts)

        # Determine search mode
        search_mode = "hybrid"  # default
        if flags.get("semantic"):
            search_mode = "semantic"
        elif flags.get("keyword"):
            search_mode = "keyword"

        # Temporal constraints
        since = flags.get("since")
        until = flags.get("until")

        # Recency boost control
        apply_recency = not flags.get("no-recency", False)

        # Metadata pre-filters
        project_filter = flags.get("project")
        tags_filter = flags.get("tags")

        rows, search_id, temporal_range = search_memories(
            query, mode=search_mode, since=since, until=until, apply_recency_boost=apply_recency,
            project=project_filter, tags=tags_filter
        )

        # Show temporal filter info if applied
        if temporal_range:
            start, end = temporal_range
            print(f"📅 Filtered to: {start.strftime('%Y-%m-%d %H:%M')} → {end.strftime('%Y-%m-%d %H:%M')}\n")

        if rows:
            full_mode = flags.get("full", False)
            show_tokens = flags.get("tokens", False)  # --tokens flag to show individual estimates

            # Token budget: truncate results to fit within budget (claude-mem Steal #2)
            budget = flags.get("budget")
            if budget:
                try:
                    budget_limit = int(budget)
                    total_tokens = 0
                    truncated_rows = []
                    for r in rows:
                        tokens = estimate_tokens(r['content'])
                        if total_tokens + tokens <= budget_limit:
                            truncated_rows.append(r)
                            total_tokens += tokens
                        else:
                            # Stop when budget exceeded
                            break

                    if len(truncated_rows) < len(rows):
                        print(f"⚠️  Token budget: showing {len(truncated_rows)}/{len(rows)} results (fits in ~{total_tokens}/{budget_limit} tokens)\n")
                    rows = truncated_rows
                except ValueError:
                    pass  # Invalid budget, ignore

            for r in rows:
                if full_mode:
                    print(format_row(r))
                else:
                    print(format_row_compact(r, show_tokens=show_tokens))
                # Related in compact mode too
                if not full_mode:
                    for rel in get_related(r["id"]):
                        print(f"  -> #{rel['id']}: {rel['content'][:60]}")
                else:
                    for rel in get_related(r["id"]):
                        print(f"      -> #{rel['id']} ({rel['relation_type']}): {rel['content'][:80]}")

            # Show token economics summary (always enabled)
            show_token_economics(rows, compact=not full_mode)

            # Output search_id for feedback tracking (can be parsed by hooks)
            print(f"\n[search_id:{search_id}]")
        else:
            print("No memories found.")

    elif cmd == "get" and len(sys.argv) >= 3:
        print_memory_full(int(sys.argv[2]))

    elif cmd == "passport" and len(sys.argv) >= 3:
        from .passport import get_passport, display_passport
        try:
            mem_id = int(sys.argv[2])
            passport = get_passport(mem_id)
            display_passport(passport)
        except ValueError:
            print(f"Error: Invalid memory ID '{sys.argv[2]}'")
        except Exception as e:
            print(f"Error generating passport: {e}")

    elif cmd == "list":
        flags, _ = parse_flags(sys.argv, 2)
        rows = list_memories(
            category=flags.get("category"),
            project=flags.get("project"),
            tag=flags.get("tag"),
            stale_only="stale" in sys.argv,
            expired_only="--expired" in sys.argv,
            sort_by_proof="--proven" in sys.argv,
        )
        for r in rows:
            print(format_row(r))
        print(f"\n({len(rows)} memories)")

    elif cmd == "update" and len(sys.argv) >= 4:
        update_memory(int(sys.argv[2]), " ".join(sys.argv[3:]))

    elif cmd == "delete" and len(sys.argv) >= 3:
        delete_memory(int(sys.argv[2]))

    elif cmd == "tag" and len(sys.argv) >= 4:
        tag_memory(int(sys.argv[2]), sys.argv[3])

    elif cmd == "relate" and len(sys.argv) >= 4:
        rel_type = sys.argv[4] if len(sys.argv) > 4 else "related"
        relate_memories(int(sys.argv[2]), int(sys.argv[3]), rel_type)

    elif cmd == "conflicts":
        conflicts = find_conflicts()
        if conflicts:
            print(f"Potential conflicts ({len(conflicts)} found):\n")
            for c in conflicts:
                suggest = "MERGE" if c["score"] > 0.70 else "REVIEW"
                print(f"  #{c['id1']} vs #{c['id2']} ({c['score']:.0%} similar) [{c['project']}/{c['category']}]")
                print(f"    A: {c['content1'][:80]}...")
                print(f"    B: {c['content2'][:80]}...")
                print(f"    Suggest: {suggest} (memory-tool merge {c['id1']} {c['id2']})\n")
        else:
            print("No conflicts found.")

    elif cmd == "merge" and len(sys.argv) >= 4:
        merge_memories(int(sys.argv[2]), int(sys.argv[3]))

    elif cmd == "supersede" and len(sys.argv) >= 4:
        supersede_memory(int(sys.argv[2]), int(sys.argv[3]))

    elif cmd == "pending":
        rows = list_memories(category="pending")
        for r in rows:
            print(format_row(r))
        print(f"\n({len(rows)} pending items)")

    elif cmd == "projects":
        conn = get_db()
        projects = conn.execute("""
            SELECT project, COUNT(*) as count,
                   GROUP_CONCAT(DISTINCT category) as categories,
                   SUM(CASE WHEN category='pending' THEN 1 ELSE 0 END) as pending,
                   SUM(CASE WHEN stale=1 THEN 1 ELSE 0 END) as stale
            FROM memories WHERE active = 1 AND project IS NOT NULL
            GROUP BY project ORDER BY count DESC
        """).fetchall()
        conn.close()
        for p in projects:
            print(f"  {p['project']}: {p['count']} memories, {p['pending']} pending, {p['stale']} stale ({p['categories']})")

    elif cmd == "topics":
        export_topics()
        print("Exported topic files")

    elif cmd == "export":
        flags, _ = parse_flags(sys.argv, 2)
        project = flags.get("project") or detect_project()
        export_memory_md(project)
        focus = f" (focused on {project})" if project else ""
        print(f"Exported to {MEMORY_MD_PATH}{focus}")

    elif cmd == "stats":
        conn = get_db()
        stats = conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN active = 1 THEN 1 ELSE 0 END) as active,
                   SUM(CASE WHEN stale = 1 AND active = 1 THEN 1 ELSE 0 END) as stale,
                   SUM(CASE WHEN expires_at IS NOT NULL AND expires_at < datetime('now') AND active = 1 THEN 1 ELSE 0 END) as expired,
                   COUNT(DISTINCT project) as projects,
                   COUNT(DISTINCT category) as categories,
                   SUM(access_count) as total_accesses
            FROM memories
        """).fetchone()
        cats = conn.execute("""
            SELECT category, COUNT(*) as count, SUM(access_count) as accesses
            FROM memories WHERE active = 1 GROUP BY category ORDER BY count DESC
        """).fetchall()
        relations = conn.execute("SELECT COUNT(*) as c FROM memory_relations").fetchone()["c"]
        snapshots = conn.execute("SELECT COUNT(*) as c FROM session_snapshots").fetchone()["c"]
        sources = conn.execute("""
            SELECT source, COUNT(*) as c FROM memories WHERE active = 1 GROUP BY source ORDER BY c DESC
        """).fetchall()
        topic_keys = conn.execute("SELECT COUNT(*) as c FROM memories WHERE topic_key IS NOT NULL AND active = 1").fetchone()["c"]
        # Backup info
        backup_count = len(list(BACKUP_DIR.glob("memories_*.db"))) if BACKUP_DIR.exists() else 0

        # Vector index status
        vec_indexed = 0
        if has_vec_support():
            try:
                vec_indexed = conn.execute("SELECT COUNT(*) as c FROM memory_vec").fetchone()["c"]
            except sqlite3.OperationalError:
                pass  # Table doesn't exist yet

        # Graph stats
        g_stats = graph_stats()

        conn.close()

        print(f"Memories: {stats['total']} total ({stats['active']} active, {stats['stale']} stale, {stats['expired'] or 0} expired)")
        print(f"Projects: {stats['projects']} | Categories: {stats['categories']}")
        print(f"Relations: {relations} | Snapshots: {snapshots} | Backups: {backup_count}")
        print(f"Topic keys: {topic_keys}")
        print(f"Total accesses: {stats['total_accesses'] or 0}")
        print(f"Graph: {g_stats['entities']} entities, {g_stats['relationships']} relationships, {g_stats['facts']} facts, {g_stats['memory_links']} memory links")

        # Vector search status
        if has_vec_support():
            vec_pct = (vec_indexed / stats['active'] * 100) if stats['active'] > 0 else 0
            print(f"Vector index: {vec_indexed}/{stats['active']} embeddings ({vec_pct:.0f}%)")
        else:
            print("Vector index: Not available (install sqlite-vec, onnxruntime, tokenizers, numpy)")
        # Bridge status
        sync_state = load_sync_state()
        if sync_state.get('last_sync'):
            last_sync = sync_state['last_sync'][:16]
            openclaw_files = len(list(OPENCLAW_MEMORY_DIR.glob("*.md"))) if OPENCLAW_MEMORY_DIR.exists() else 0
            print(f"Bridge: last sync {last_sync}, {openclaw_files} OpenClaw files")
        else:
            print("Bridge: never synced (run 'memory-tool sync')")

        # Corrections status
        conn = get_db()
        try:
            corrections_total = conn.execute("SELECT COUNT(*) as c FROM corrections").fetchone()["c"]
            corrections_pending = conn.execute("SELECT COUNT(*) as c FROM corrections WHERE status = 'pending'").fetchone()["c"]
            if corrections_total:
                print(f"Corrections: {corrections_total} total ({corrections_pending} pending)")
        except sqlite3.OperationalError:
            pass  # corrections table might not exist in older versions
        conn.close()

        print("\nBy category:")
        for c in cats:
            print(f"  {c['category']}: {c['count']} (accessed {c['accesses'] or 0}x)")
        print("\nBy source:")
        for s in sources:
            print(f"  {s['source']}: {s['c']}")

        # Search quality summary
        try:
            from .feedback import get_search_quality_stats
            search_stats = get_search_quality_stats()
            if search_stats['hit_rate_all']['searches'] > 0:
                print(f"\nSearch Quality:")
                print(f"  Hit rate (7d): {search_stats['hit_rate_7d']['rate']:.0%} ({search_stats['hit_rate_7d']['searches']} searches)")
                print(f"  Hit rate (all): {search_stats['hit_rate_all']['rate']:.0%} ({search_stats['hit_rate_all']['searches']} searches)")
        except Exception:
            pass  # Feedback module might not be available

    elif cmd == "stale":
        rows = get_stale()
        if rows:
            for r in rows:
                print(format_row(r))
            print(f"\n({len(rows)} stale items)")
            print("Actions: 'memory-tool delete <id>' or 'memory-tool update <id> ...'")
        else:
            print("No stale memories.")

    elif cmd == "decay":
        run_decay()

    elif cmd == "consolidate":
        print("🧠 Running memory consolidation...")
        conn = get_db()
        results = consolidate_memories(conn)
        conn.close()
        print(f"\nConsolidation complete:")
        print(f"  📦 Merged: {results['merged']} near-duplicates")
        print(f"  💡 Insights: {results['insights']} patterns discovered")
        print(f"  🔗 Connections: {results['connections']} strengthened")
        print(f"  🗑️  Pruned: {results['pruned']} low-value memories")
        total = sum(results.values())
        if total == 0:
            print("\n  Memory is clean — nothing to consolidate. 🧘")

    elif cmd == "snapshot" and len(sys.argv) >= 3:
        flags, content_parts = parse_flags(sys.argv, 2)
        summary = " ".join(content_parts) if content_parts else " ".join(sys.argv[2:])
        project = flags.get("project") or detect_project()
        save_snapshot(summary, project)
        export_memory_md(project)

    elif cmd == "auto-snapshot":
        auto_snapshot()

    elif cmd == "snapshots":
        flags, _ = parse_flags(sys.argv, 2)
        limit = int(flags.get("limit", 5))
        snaps = get_snapshots(limit)
        for s in snaps:
            proj = f" [{s['project']}]" if s["project"] else ""
            files = f"\n    Files: {s['files_touched'][:150]}" if s["files_touched"] else ""
            print(f"  [{s['created_at'][:16]}]{proj} {s['summary']}{files}")
        print(f"\n({len(snaps)} snapshots)")

    elif cmd == "detect-project":
        print(detect_project() or "Unknown project")

    elif cmd == "gc":
        garbage_collect(int(sys.argv[2]) if len(sys.argv) >= 3 else 180)

    elif cmd == "log-error" and len(sys.argv) >= 4:
        command = sys.argv[2]
        error = " ".join(sys.argv[3:])
        flags, _ = parse_flags(sys.argv, 4)
        log_error(command, error, project=flags.get("project"))

    elif cmd == "import-md" and len(sys.argv) >= 3:
        import_session_md(sys.argv[2])

    elif cmd == "backup":
        backup_db()

    elif cmd == "restore" and len(sys.argv) >= 3:
        restore_db(sys.argv[2])

    elif cmd == "reindex":
        reindex_embeddings()

    elif cmd == "graph":
        # Graph intelligence subcommands
        if len(sys.argv) < 3:
            # Show graph summary
            g_stats = graph_stats()
            print(f"Graph Intelligence Summary:")
            print(f"  Entities: {g_stats['entities']}")
            print(f"  Relationships: {g_stats['relationships']}")
            print(f"  Facts: {g_stats['facts']}")
            print(f"  Memory links: {g_stats['memory_links']}")
            if g_stats['by_type']:
                print(f"\n  By type:")
                for t in g_stats['by_type']:
                    print(f"    {t['type']}: {t['count']}")
        else:
            subcmd = sys.argv[2]

            if subcmd == "add" and len(sys.argv) >= 5:
                entity_type = sys.argv[3]
                name = sys.argv[4]
                summary = " ".join(sys.argv[5:]) if len(sys.argv) > 5 else ""
                entity_id = graph_add_entity(name, entity_type, summary)
                print(f"Added entity #{entity_id}: {name} ({entity_type})")

            elif subcmd == "rel" and len(sys.argv) >= 6:
                from_name = sys.argv[3]
                relation_type = sys.argv[4]
                to_name = sys.argv[5]
                note = " ".join(sys.argv[6:]) if len(sys.argv) > 6 else ""
                success = graph_add_relationship(from_name, to_name, relation_type, note)
                if success:
                    print(f"Added relationship: {from_name} --{relation_type}--> {to_name}")
                else:
                    print("Failed to add relationship")

            elif subcmd == "fact" and len(sys.argv) >= 6:
                entity_name = sys.argv[3]
                key = sys.argv[4]
                value = " ".join(sys.argv[5:])
                success = graph_set_fact(entity_name, key, value)
                if success:
                    print(f"Set fact: {entity_name}.{key} = {value}")
                else:
                    print("Failed to set fact")

            elif subcmd == "get" and len(sys.argv) >= 4:
                name = sys.argv[3]
                entity = graph_get_entity(name)
                if entity:
                    e = entity['entity']
                    print(f"\n{e['name']} ({e['type']}) - Importance: {e['importance']}")
                    if e['summary']:
                        print(f"  Summary: {e['summary']}")
                    print(f"  Created: {e['created_at'][:16]} | Updated: {e['updated_at'][:16]}")

                    if entity['facts']:
                        print(f"\n  Facts ({len(entity['facts'])}):")
                        for f in entity['facts']:
                            conf = f" (confidence: {f['confidence']})" if f['confidence'] < 1.0 else ""
                            print(f"    {f['key']}: {f['value']}{conf}")

                    if entity['outgoing']:
                        print(f"\n  Relationships (outgoing):")
                        for r in entity['outgoing']:
                            note = f" - {r['note']}" if r['note'] else ""
                            print(f"    --{r['relation_type']}--> {r['to_name']} ({r['to_type']}){note}")

                    if entity['incoming']:
                        print(f"\n  Relationships (incoming):")
                        for r in entity['incoming']:
                            note = f" - {r['note']}" if r['note'] else ""
                            print(f"    <--{r['relation_type']}-- {r['from_name']} ({r['from_type']}){note}")

                    if entity['memories']:
                        print(f"\n  Linked memories ({len(entity['memories'])}):")
                        for m in entity['memories']:
                            print(f"    #{m['id']} [{m['category']}] {m['content'][:80]}")
                else:
                    print(f"Entity not found: {name}")

            elif subcmd == "list":
                entity_type = sys.argv[3] if len(sys.argv) >= 4 else None
                entities = graph_list_entities(entity_type)
                if entities:
                    for e in entities:
                        summary = f" - {e['summary'][:60]}" if e['summary'] else ""
                        print(f"  {e['name']} ({e['type']}) [importance: {e['importance']}]{summary}")
                    print(f"\n({len(entities)} entities)")
                else:
                    print("No entities found")

            elif subcmd == "delete" and len(sys.argv) >= 4:
                name = sys.argv[3]
                success = graph_delete_entity(name)
                if success:
                    print(f"Deleted entity: {name}")
                else:
                    print(f"Entity not found: {name}")

            elif subcmd == "spread" and len(sys.argv) >= 4:
                name = sys.argv[3]
                depth = int(sys.argv[4]) if len(sys.argv) >= 5 else 2
                results = graph_spread(name, depth)
                if results:
                    print(f"Spreading activation from '{name}' (depth={depth}):")
                    for e in results:
                        print(f"  [{e['activation']:.2f}] {e['name']} ({e['type']}) - {e['summary'][:60] if e['summary'] else '(no summary)'}")
                    print(f"\n({len(results)} entities)")
                else:
                    print(f"No connected entities found or entity '{name}' doesn't exist")

            elif subcmd == "link" and len(sys.argv) >= 5:
                memory_id = int(sys.argv[3])
                entity_name = sys.argv[4]
                success = link_memory_to_entity(memory_id, entity_name)
                if success:
                    print(f"Linked memory #{memory_id} to entity '{entity_name}'")
                else:
                    print("Failed to link memory to entity")

            elif subcmd == "auto-link":
                total_links, total_mems = graph_auto_link_all()
                print(f"Auto-linked {total_links} connections across {total_mems} memories")

            elif subcmd == "import-openclaw":
                graph_import_openclaw()

            elif subcmd == "stats":
                g_stats = graph_stats()
                print(f"Graph Statistics:")
                print(f"  Entities: {g_stats['entities']}")
                print(f"  Relationships: {g_stats['relationships']}")
                print(f"  Facts: {g_stats['facts']}")
                print(f"  Memory links: {g_stats['memory_links']}")
                if g_stats['by_type']:
                    print(f"\n  Entities by type:")
                    for t in g_stats['by_type']:
                        print(f"    {t['type']}: {t['count']}")

            else:
                print(f"Unknown graph subcommand: {subcmd}")
                print("\nGraph commands:")
                print("  memory-tool graph                         # Show graph summary")
                print("  memory-tool graph add <type> <name> [summary]")
                print("  memory-tool graph rel <from> <rel_type> <to> [note]")
                print("  memory-tool graph fact <entity> <key> <value>")
                print("  memory-tool graph get <name>")
                print("  memory-tool graph list [type]")
                print("  memory-tool graph delete <name>")
                print("  memory-tool graph spread <name> [depth]")
                print("  memory-tool graph link <memory_id> <entity_name>")
                print("  memory-tool graph auto-link")
                print("  memory-tool graph import-openclaw")
                print("  memory-tool graph stats")

    elif cmd == "sync":
        sync_bidirectional()

    elif cmd == "sync-to":
        sync_to_openclaw()

    elif cmd == "sync-from":
        sync_from_openclaw()

    elif cmd == "run":
        # Run tracking subcommands
        if len(sys.argv) < 3:
            print("Usage: memory-tool run <subcommand>")
            print("Subcommands: start, step, complete, fail, list, show, cancel")
            sys.exit(1)
            
        subcmd = sys.argv[2]
        
        if subcmd == "start" and len(sys.argv) >= 4:
            task = sys.argv[3]
            flags, _ = parse_flags(sys.argv, 4)
            agent = flags.get("agent", "claw")
            project = flags.get("project")
            tags = flags.get("tags", "")
            
            run_id = start_run(task, agent, project, tags)
            print(f"Started run #{run_id}")
            
        elif subcmd == "step" and len(sys.argv) >= 5:
            try:
                run_id = int(sys.argv[3])
                step_description = " ".join(sys.argv[4:])
                success = add_run_step(run_id, step_description)
                if success:
                    print(f"Added step to run #{run_id}")
                else:
                    print(f"Run #{run_id} not found")
            except ValueError:
                print("Invalid run ID")
                
        elif subcmd == "complete" and len(sys.argv) >= 5:
            try:
                run_id = int(sys.argv[3])
                outcome = " ".join(sys.argv[4:])
                complete_run(run_id, outcome)
                print(f"Completed run #{run_id}")
            except ValueError:
                print("Invalid run ID")
                
        elif subcmd == "fail" and len(sys.argv) >= 5:
            try:
                run_id = int(sys.argv[3])
                reason = " ".join(sys.argv[4:])
                fail_run(run_id, reason)
                print(f"Failed run #{run_id}")
            except ValueError:
                print("Invalid run ID")
                
        elif subcmd == "cancel" and len(sys.argv) >= 4:
            try:
                run_id = int(sys.argv[3])
                cancel_run(run_id)
                print(f"Cancelled run #{run_id}")
            except ValueError:
                print("Invalid run ID")
                
        elif subcmd == "list":
            flags, _ = parse_flags(sys.argv, 3)
            status = flags.get("status")
            project = flags.get("project")
            limit = int(flags.get("limit", 10))
            
            runs = list_runs(status, project, limit)
            
            if runs:
                print(f"{'ID':<4} {'Task':<50} {'Agent':<8} {'Status':<12} {'Started':<16} {'Duration':<12}")
                print("-" * 108)
                for r in runs:
                    task_preview = r['task'][:47] + "..." if len(r['task']) > 50 else r['task']
                    duration = format_duration(r['started_at'], r['completed_at'])
                    started_short = r['started_at'][:16] if r['started_at'] else "unknown"
                    print(f"{r['id']:<4} {task_preview:<50} {r['agent']:<8} {r['status']:<12} {started_short:<16} {duration:<12}")
                print(f"\n({len(runs)} runs)")
            else:
                print("No runs found")
                
        elif subcmd == "show" and len(sys.argv) >= 4:
            try:
                run_id = int(sys.argv[3])
                run = show_run(run_id)
                if run:
                    print(f"\n=== Run #{run['id']} ===")
                    print(f"Task: {run['task']}")
                    print(f"Agent: {run['agent']}")
                    print(f"Status: {run['status']}")
                    print(f"Started: {run['started_at']}")
                    if run['completed_at']:
                        print(f"Completed: {run['completed_at']}")
                        duration = format_duration(run['started_at'], run['completed_at'])
                        print(f"Duration: {duration}")
                    elif run['status'] == 'running':
                        duration = format_duration(run['started_at'])
                        print(f"Running for: {duration}")
                    if run['project']:
                        print(f"Project: {run['project']}")
                    if run['tags']:
                        print(f"Tags: {run['tags']}")
                    if run['outcome']:
                        print(f"Outcome: {run['outcome']}")
                    
                    # Parse and display steps
                    try:
                        steps = json.loads(run['steps'])
                        if steps:
                            print(f"\nSteps ({len(steps)}):")
                            for i, step in enumerate(steps, 1):
                                print(f"  {i}. {step}")
                    except (json.JSONDecodeError, TypeError):
                        if run['steps'] and run['steps'] != '[]':
                            print(f"Steps: {run['steps']}")
                    print()
                else:
                    print(f"Run #{run_id} not found")
            except ValueError:
                print("Invalid run ID")
        else:
            print(f"Unknown run subcommand: {subcmd}")
            print("\nRun commands:")
            print("  memory-tool run start \"task description\" [--agent claw|claude] [--project X] [--tags x,y]")
            print("  memory-tool run step <id> \"step description\"")
            print("  memory-tool run complete <id> \"outcome summary\"")
            print("  memory-tool run fail <id> \"reason\"")
            print("  memory-tool run list [--status running|completed|failed] [--project X] [--limit 10]")
            print("  memory-tool run show <id>")
            print("  memory-tool run cancel <id>")

    elif cmd == "importance":
        show_importance_ranking()

    elif cmd == "retention":
        # Show memories sorted by retention (lowest first)
        conn = get_db()
        now = datetime.now()
        rows = conn.execute("""
            SELECT id, category, project, content, fsrs_stability, fsrs_difficulty,
                   last_accessed_at, updated_at, access_count, priority
            FROM memories WHERE active = 1
            ORDER BY priority DESC
        """).fetchall()

        scored = []
        for r in rows:
            stability = r["fsrs_stability"] or 1.0
            last_acc = r["last_accessed_at"] or r["updated_at"]
            try:
                last_dt = datetime.fromisoformat(last_acc.replace('Z', '+00:00')).replace(tzinfo=None)
                elapsed = (now - last_dt).total_seconds() / 86400
            except (ValueError, AttributeError):
                elapsed = 90  # Fallback for invalid date format
            retention = fsrs_retention(stability, elapsed)
            scored.append((retention, r))

        scored.sort(key=lambda x: x[0])

        print("Memory Retention Report (lowest first — needs reinforcement)")
        print("=" * 60)
        for retention, r in scored[:20]:
            bar = "█" * int(retention * 10) + "░" * (10 - int(retention * 10))
            content = r["content"][:60]
            cat = r["category"][:5]
            proj = f"[{r['project'][:8]}]" if r["project"] else ""
            print(f"  #{r['id']:>3} {bar} {retention*100:>3.0f}% [{cat}]{proj} {content}")

        print(f"\n{len(scored)} memories total. Showing bottom 20.")
        conn.close()

    elif cmd == "next":
        suggest_next()

    elif cmd == "focus" and len(sys.argv) >= 3:
        from .focus import cmd_focus
        flags, topic_parts = parse_flags(sys.argv, 2)
        topic = " ".join(topic_parts) if topic_parts else sys.argv[2]
        full = flags.get("full", False)
        cmd_focus(topic, full)

    elif cmd == "dream":
        cmd_dream()

    elif cmd == "correct":
        if len(sys.argv) < 3:
            print("Usage: memory-tool correct \"<correction text>\"")
            sys.exit(1)
        text = " ".join(sys.argv[2:])
        conn = get_db()
        conn.execute(
            "INSERT INTO corrections (raw_text, correction) VALUES (?, ?)",
            (text, text)
        )
        conn.commit()
        conn.close()
        print(f"✅ Correction queued: {text}")
        print("Run 'memory-tool corrections' to review pending corrections.")

    elif cmd == "corrections":
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM corrections WHERE status = 'pending' ORDER BY created_at DESC"
        ).fetchall()
        conn.close()

        if not rows:
            print("No pending corrections. 🧠")
            sys.exit(0)

        print(f"Pending Corrections ({len(rows)})")
        print("=" * 50)
        for r in rows:
            print(f"  #{r['id']} [{r['category']}] {r['correction']}")
            print(f"     Raw: \"{r['raw_text']}\"")
            print(f"     Queued: {r['created_at']}")
            print()

        print("To apply: memory-tool apply-correction <id>")
        print("To dismiss: memory-tool dismiss-correction <id>")

    elif cmd == "apply-correction":
        if len(sys.argv) < 3:
            print("Usage: memory-tool apply-correction <id>")
            sys.exit(1)
        cid = int(sys.argv[2])
        conn = get_db()
        row = conn.execute("SELECT * FROM corrections WHERE id = ?", (cid,)).fetchone()
        if not row:
            print(f"Correction #{cid} not found.")
            conn.close()
            sys.exit(1)

        # Add as a preference/learning memory
        category = row["category"]
        content = row["correction"]

        # Use existing add_memory function
        mem_id = add_memory(category, content, tags="correction,user-feedback")

        conn.execute(
            "UPDATE corrections SET status = 'applied', applied_at = datetime('now'), memory_id = ? WHERE id = ?",
            (mem_id, cid)
        )
        conn.commit()
        conn.close()
        print(f"✅ Correction #{cid} applied as memory #{mem_id}")

    elif cmd == "dismiss-correction":
        if len(sys.argv) < 3:
            print("Usage: memory-tool dismiss-correction <id>")
            sys.exit(1)
        cid = int(sys.argv[2])
        conn = get_db()
        conn.execute("UPDATE corrections SET status = 'dismissed' WHERE id = ?", (cid,))
        conn.commit()
        conn.close()
        print(f"Correction #{cid} dismissed.")

    elif cmd == "detect":
        if len(sys.argv) < 3:
            print("Usage: memory-tool detect \"<text to scan>\"")
            sys.exit(1)
        text = " ".join(sys.argv[2:])
        result = detect_correction(text)
        if result:
            print(f"✅ Correction detected!")
            print(f"  Type: {result['type']}")
            print(f"  Match: {result['full_match']}")
            print(f"  Extracted: {result['correction']}")

            # Auto-queue it
            conn = get_db()
            conn.execute(
                "INSERT INTO corrections (raw_text, correction, category) VALUES (?, ?, 'preference')",
                (text, result['correction'])
            )
            conn.commit()
            conn.close()
            print(f"  → Queued as pending correction")
        else:
            print("No correction pattern detected.")

    elif cmd == "capture-correction":
        text = " ".join(sys.argv[2:])
        if not text:
            print("Usage: memory-tool capture-correction <text>")
            sys.exit(1)
        cmd_capture_correction(text)

    elif cmd == "feedback" and len(sys.argv) >= 4 and sys.argv[2].isdigit():
        # memory-tool feedback <search_id> <used_id1,used_id2,...>
        search_id = int(sys.argv[2])
        used_ids = [int(x.strip()) for x in sys.argv[3].split(',') if x.strip()]
        from .feedback import log_search_feedback
        log_search_feedback(search_id, used_ids)
        print(f"Feedback logged for search #{search_id}: {len(used_ids)} memories marked as used")

    elif cmd == "search-quality":
        from .feedback import get_search_quality_stats
        stats = get_search_quality_stats()

        print("Search Quality Report")
        print("=" * 70)

        # Hit rates by period
        print("\nOverall Hit Rates:")
        print(f"  Last 7 days:  {stats['hit_rate_7d']['rate']:.1%} ({stats['hit_rate_7d']['searches']} searches)")
        print(f"  Last 30 days: {stats['hit_rate_30d']['rate']:.1%} ({stats['hit_rate_30d']['searches']} searches)")
        print(f"  All time:     {stats['hit_rate_all']['rate']:.1%} ({stats['hit_rate_all']['searches']} searches)")

        # Most helpful memories
        if stats['most_helpful']:
            print("\nMost Helpful Memories (high hit rate, 5+ retrievals):")
            for m in stats['most_helpful'][:5]:
                content_preview = m['content'][:60] + "..." if len(m['content']) > 60 else m['content']
                print(f"  #{m['id']:>3} [{m['category']:<8}] {m['hit_rate']:.0%} ({m['used_count']}/{m['retrieve_count']}) {content_preview}")

        # Least helpful memories
        if stats['least_helpful']:
            print("\nLeast Helpful Memories (low hit rate, 10+ retrievals):")
            for m in stats['least_helpful'][:5]:
                content_preview = m['content'][:60] + "..." if len(m['content']) > 60 else m['content']
                print(f"  #{m['id']:>3} [{m['category']:<8}] {m['hit_rate']:.0%} ({m['used_count']}/{m['retrieve_count']}) {content_preview}")

        # Search patterns
        if stats['search_patterns']:
            print("\nMost Common Queries:")
            for p in stats['search_patterns'][:5]:
                print(f"  '{p['query'][:40]}' - {p['search_count']} searches, {p['avg_hit_rate']:.0%} avg hit rate")

        # Failing queries
        if stats['failing_queries']:
            print("\nRecent Failing Queries (0% hit rate):")
            for q in stats['failing_queries'][:5]:
                print(f"  '{q['query'][:50]}' [{q['search_type']}] - {q['result_count']} results but none used")

    elif cmd == "feedback" and len(sys.argv) == 3 and sys.argv[2] == "suggestions":
        # memory-tool feedback suggestions
        from .feedback import get_improvement_suggestions
        suggestions = get_improvement_suggestions()

        print("Improvement Suggestions")
        print("=" * 70)

        # Deprecation candidates
        if suggestions['deprecation_candidates']:
            print("\n🗑️  Deprecation Candidates (retrieved often, never used):")
            for m in suggestions['deprecation_candidates']:
                print(f"  #{m['id']:>3} [{m['category']:<8}] {m['retrieved_count']} retrievals")
                print(f"      {m['content']}")
                print(f"      Suggest: memory-tool delete {m['id']}")
        else:
            print("\n✓ No deprecation candidates found")

        # Knowledge gaps
        if suggestions['knowledge_gaps']:
            print("\n🔍 Knowledge Gaps (queries with no results):")
            for g in suggestions['knowledge_gaps']:
                print(f"  '{g['query']}' - {g['attempt_count']} failed searches")
                print(f"      Suggest: Add memory covering this topic")
        else:
            print("\n✓ No knowledge gaps found")

        # Tag suggestions
        if suggestions['tag_suggestions']:
            print("\n🏷️  Tag Suggestions (commonly searched terms):")
            for t in suggestions['tag_suggestions']:
                print(f"  '{t['keyword']}' - {t['search_count']} searches")
        else:
            print("\n✓ No tag suggestions")

    elif cmd == "feedback" and len(sys.argv) == 3 and sys.argv[2] == "reset":
        # memory-tool feedback reset
        conn = get_db()
        count = conn.execute("SELECT COUNT(*) as c FROM search_log").fetchone()['c']
        conn.execute("DELETE FROM search_log")
        conn.commit()
        conn.close()
        print(f"Cleared {count} search log entries")

    elif cmd == "feedback" and len(sys.argv) >= 3 and sys.argv[2] in ["good", "bad", "meh"]:
        # memory-tool feedback good/bad/meh "reason"
        rating = sys.argv[2]
        reason = sys.argv[3] if len(sys.argv) >= 4 else None

        # Get most recent memory
        conn = get_db()
        last_memory = conn.execute("""
            SELECT id FROM memories
            WHERE active = 1
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()
        linked_memory_id = last_memory['id'] if last_memory else None

        # Try to get session ID from metrics file
        session_id = None
        try:
            from pathlib import Path
            metrics_file = Path("/tmp/claude-session-metrics.json")
            if metrics_file.exists():
                data = json.loads(metrics_file.read_text())
                session_id = data.get('startedAt', None)
        except Exception:
            pass

        # Insert feedback
        conn.execute("""
            INSERT INTO feedback (rating, reason, session_id, linked_memory_id)
            VALUES (?, ?, ?, ?)
        """, (rating, reason, session_id, linked_memory_id))
        conn.commit()

        memory_info = f" (linked to memory #{linked_memory_id})" if linked_memory_id else ""
        print(f"✓ Feedback recorded: {rating}{memory_info}")
        if reason:
            print(f"  Reason: {reason}")
        conn.close()

    elif cmd == "feedback" and len(sys.argv) == 2:
        # memory-tool feedback (no args) - show recent feedback
        conn = get_db()
        rows = conn.execute("""
            SELECT f.id, f.rating, f.reason, f.created_at, f.linked_memory_id,
                   m.content as memory_content, m.category
            FROM feedback f
            LEFT JOIN memories m ON f.linked_memory_id = m.id
            ORDER BY f.created_at DESC
            LIMIT 10
        """).fetchall()
        conn.close()

        if rows:
            print("Recent Feedback")
            print("=" * 70)
            for r in rows:
                created = r['created_at'][:16] if r['created_at'] else "unknown"
                rating_emoji = "✓" if r['rating'] == "good" else "✗" if r['rating'] == "bad" else "~"
                print(f"\n{rating_emoji} #{r['id']} [{r['rating'].upper()}] {created}")
                if r['reason']:
                    print(f"  Reason: {r['reason']}")
                if r['linked_memory_id']:
                    content = r['memory_content'][:60] + "..." if r['memory_content'] and len(r['memory_content']) > 60 else r['memory_content']
                    print(f"  Memory #{r['linked_memory_id']} [{r['category']}]: {content}")
            print(f"\n({len(rows)} feedback entries)")
        else:
            print("No feedback recorded yet.")

    elif cmd == "feedback" and len(sys.argv) == 3 and sys.argv[2] == "--stats":
        # memory-tool feedback --stats
        conn = get_db()
        stats = conn.execute("""
            SELECT
                rating,
                COUNT(*) as count,
                COUNT(DISTINCT session_id) as sessions,
                COUNT(DISTINCT linked_memory_id) as unique_memories
            FROM feedback
            GROUP BY rating
        """).fetchall()
        total = conn.execute("SELECT COUNT(*) as c FROM feedback").fetchone()['c']
        conn.close()

        if total > 0:
            print("Feedback Statistics")
            print("=" * 70)
            for s in stats:
                pct = (s['count'] / total * 100) if total > 0 else 0
                print(f"  {s['rating'].upper()}: {s['count']} ({pct:.0f}%) — {s['sessions']} sessions, {s['unique_memories']} memories")
            print(f"\nTotal: {total} feedback entries")
        else:
            print("No feedback recorded yet.")

    elif cmd == "feedback-stats":
        # Alias for search-quality
        from .feedback import get_search_quality_stats
        stats = get_search_quality_stats()

        print("Search Quality Report")
        print("=" * 70)

        # Hit rates by period
        print("\nOverall Hit Rates:")
        print(f"  Last 7 days:  {stats['hit_rate_7d']['rate']:.1%} ({stats['hit_rate_7d']['searches']} searches)")
        print(f"  Last 30 days: {stats['hit_rate_30d']['rate']:.1%} ({stats['hit_rate_30d']['searches']} searches)")
        print(f"  All time:     {stats['hit_rate_all']['rate']:.1%} ({stats['hit_rate_all']['searches']} searches)")

        # Most helpful memories
        if stats['most_helpful']:
            print("\nMost Helpful Memories (high hit rate, 5+ retrievals):")
            for m in stats['most_helpful'][:5]:
                content_preview = m['content'][:60] + "..." if len(m['content']) > 60 else m['content']
                print(f"  #{m['id']:>3} [{m['category']:<8}] {m['hit_rate']:.0%} ({m['used_count']}/{m['retrieve_count']}) {content_preview}")

        # Least helpful memories
        if stats['least_helpful']:
            print("\nLeast Helpful Memories (low hit rate, 10+ retrievals):")
            for m in stats['least_helpful'][:5]:
                content_preview = m['content'][:60] + "..." if len(m['content']) > 60 else m['content']
                print(f"  #{m['id']:>3} [{m['category']:<8}] {m['hit_rate']:.0%} ({m['used_count']}/{m['retrieve_count']}) {content_preview}")

        # Search patterns
        if stats['search_patterns']:
            print("\nMost Common Queries:")
            for p in stats['search_patterns'][:5]:
                print(f"  '{p['query'][:40]}' - {p['search_count']} searches, {p['avg_hit_rate']:.0%} avg hit rate")

        # Failing queries
        if stats['failing_queries']:
            print("\nRecent Failing Queries (0% hit rate):")
            for q in stats['failing_queries'][:5]:
                print(f"  '{q['query'][:50]}' [{q['search_type']}] - {q['result_count']} results but none used")

    elif cmd == "gaps":
        # Show knowledge gaps - queries with no results
        from .feedback import get_improvement_suggestions
        suggestions = get_improvement_suggestions()

        print("Knowledge Gaps (searches with poor results)")
        print("=" * 70)

        if suggestions['knowledge_gaps']:
            print("\nQueries with zero results:")
            for g in suggestions['knowledge_gaps']:
                print(f"  '{g['query']}' - {g['attempt_count']} failed attempt(s)")
                print(f"    Type: {g['search_type']}")
                print(f"    Suggestion: Add memory covering this topic")
                print()
        else:
            print("\n✓ No knowledge gaps found")

        if suggestions['deprecation_candidates']:
            print("\nMemories retrieved often but never used (false positives):")
            for m in suggestions['deprecation_candidates'][:5]:
                print(f"  #{m['id']:>3} [{m['category']:<8}] {m['retrieved_count']} retrievals")
                print(f"      {m['content']}")
                print(f"      Suggestion: Consider deletion or rewrite")
                print()

    elif cmd == "hot":
        # Show most frequently accessed memories (immune to decay)
        conn = get_db()
        rows = conn.execute("""
            SELECT id, category, project, content, access_count, priority, imp_score
            FROM memories
            WHERE active = 1 AND access_count >= 5
            ORDER BY access_count DESC
            LIMIT 20
        """).fetchall()
        conn.close()

        if rows:
            print("Hot Memories (5+ accesses, immune to decay)")
            print("=" * 70)
            for r in rows:
                content = r['content'][:50] + "..." if len(r['content']) > 50 else r['content']
                cat = r['category'][:8]
                proj = f"[{r['project'][:10]}]" if r['project'] else ""
                print(f"  #{r['id']:>3} {r['access_count']:>3}x [{cat:<8}]{proj:<12} {content}")
            print(f"\n({len(rows)} hot memories)")
        else:
            print("No hot memories yet (need 5+ accesses)")

    elif cmd == "believe" and len(sys.argv) >= 3:
        from .beliefs import set_confidence
        statement = " ".join(sys.argv[2:])
        # Parse flags if present
        flags, content_parts = parse_flags(sys.argv, 2)
        if content_parts:
            statement = " ".join(content_parts)

        confidence = float(flags.get("confidence", 0.7))
        based_on = int(flags.get("based-on")) if flags.get("based-on") else None

        # Add as belief memory
        mem_id = add_memory(
            "belief",
            statement,
            tags="belief,explicit",
            project=flags.get("project")
        )

        # Set explicit confidence
        conn = get_db()
        set_confidence(conn, mem_id, confidence, "Explicit belief creation")
        conn.close()

        print(f"Created belief #{mem_id} with confidence {confidence:.2f}")

    elif cmd == "predict" and len(sys.argv) >= 3:
        from .beliefs import predict
        flags, content_parts = parse_flags(sys.argv, 2)
        prediction = " ".join(content_parts) if content_parts else " ".join(sys.argv[2:])

        based_on = int(flags.get("based-on")) if flags.get("based-on") else None
        confidence = float(flags.get("confidence", 0.5))
        deadline = flags.get("deadline")
        expected = flags.get("expect", "")

        conn = get_db()
        pred_id = predict(conn, prediction, based_on, confidence, deadline, expected)
        conn.close()

        print(f"Created prediction #{pred_id}")
        if deadline:
            print(f"  Deadline: {deadline}")
        print(f"  Confidence: {confidence:.2f}")

    elif cmd == "resolve" and len(sys.argv) >= 3:
        from .beliefs import resolve_prediction
        pred_id = int(sys.argv[2])
        flags, outcome_parts = parse_flags(sys.argv, 3)

        confirmed = flags.get("confirmed", False)
        refuted = flags.get("refuted", False)

        if not confirmed and not refuted:
            print("Error: Must specify --confirmed or --refuted")
            sys.exit(1)

        outcome = " ".join(outcome_parts) if outcome_parts else flags.get("outcome", "")

        conn = get_db()
        result = resolve_prediction(conn, pred_id, outcome, confirmed)
        conn.close()

        status = "confirmed" if confirmed else "refuted"
        print(f"Resolved prediction #{pred_id} as {status}")
        print(f"  Updated {result['updated']} memories via belief propagation")

    elif cmd == "beliefs":
        from .beliefs import weakest_beliefs, strongest_beliefs, belief_conflicts
        conn = get_db()

        # Check for --state filter
        if "--state" in sys.argv:
            state_idx = sys.argv.index("--state")
            if state_idx + 1 < len(sys.argv):
                state = sys.argv[state_idx + 1]
                try:
                    from .beliefs_extended import list_beliefs_by_state
                    rows = list_beliefs_by_state(conn, state)
                    print(f"Beliefs (state: {state})")
                    print("=" * 70)
                    for r in rows:
                        stmt = r['statement'][:60] + "..." if len(r['statement']) > 60 else r['statement']
                        print(f"  #{r['id']:>3} {r['confidence']:.2f} [{r['category']:<8}] {stmt}")
                    print(f"\n({len(rows)} beliefs in state '{state}')")
                except ImportError:
                    print("Extended beliefs system not available")
                except Exception as e:
                    print(f"Error: {e}")
            else:
                print("Error: --state requires a value (hypothesis/tested/validated/deprecated/refuted)")
            conn.close()

        elif "--weak" in sys.argv:
            rows = weakest_beliefs(conn, 20)
            print("Weakest Beliefs (lowest confidence)")
            print("=" * 70)
            for r in rows:
                content = r['content'][:60] + "..." if len(r['content']) > 60 else r['content']
                print(f"  #{r['id']:>3} {r['confidence']:.2f} [{r['category']:<8}] {content}")
            print(f"\n({len(rows)} beliefs)")
            conn.close()

        elif "--strong" in sys.argv:
            rows = strongest_beliefs(conn, 20)
            print("Strongest Beliefs (highest confidence)")
            print("=" * 70)
            for r in rows:
                content = r['content'][:60] + "..." if len(r['content']) > 60 else r['content']
                print(f"  #{r['id']:>3} {r['confidence']:.2f} [{r['category']:<8}] {content}")
            print(f"\n({len(rows)} beliefs)")
            conn.close()

        elif "--conflicts" in sys.argv:
            conflicts = belief_conflicts(conn)
            if conflicts:
                print("Belief Conflicts (high-confidence contradictions)")
                print("=" * 70)
                for c in conflicts:
                    print(f"  #{c['id1']} vs #{c['id2']} ({c['similarity']:.0%} similar)")
                    print(f"    A ({c['confidence1']:.2f}): {c['content1'][:60]}...")
                    print(f"    B ({c['confidence2']:.2f}): {c['content2'][:60]}...")
                    print()
                print(f"({len(conflicts)} conflicts)")
            else:
                print("No belief conflicts found.")
            conn.close()

        else:
            # Show all beliefs sorted by confidence
            rows = conn.execute("""
                SELECT id, category, content, confidence, access_count
                FROM memories
                WHERE active = 1 AND category IN ('belief', 'learning', 'decision')
                ORDER BY confidence DESC
                LIMIT 30
            """).fetchall()

            print("Beliefs (sorted by confidence)")
            print("=" * 70)
            for r in rows:
                content = r['content'][:60] + "..." if len(r['content']) > 60 else r['content']
                bar = "█" * int(r['confidence'] * 10) + "░" * (10 - int(r['confidence'] * 10))
                print(f"  #{r['id']:>3} {bar} {r['confidence']:.2f} [{r['category']:<8}] {content}")
            print(f"\n({len(rows)} beliefs)")
            conn.close()

    elif cmd == "lifecycle" and len(sys.argv) >= 4:
        # memory-tool lifecycle <id> <state>
        from .beliefs_extended import set_belief_state
        belief_id = int(sys.argv[2])
        new_state = sys.argv[3]
        reason = " ".join(sys.argv[4:]) if len(sys.argv) > 4 else None

        conn = get_db()
        try:
            set_belief_state(conn, belief_id, new_state, reason)
            print(f"✓ Belief #{belief_id} transitioned to '{new_state}'")
        except ValueError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Error: {e}")
        conn.close()

    elif cmd == "timeline":
        # memory-tool timeline [--project X] [--days N] [<id>]
        from .beliefs_extended import get_timeline, get_confidence_history, format_timeline_entry, get_timeline_summary
        flags, args = parse_flags(sys.argv, 2)

        conn = get_db()

        # Check if specific ID provided
        if args:
            identifier = int(args[0])
            # Try to determine if it's a belief or memory ID
            is_belief = conn.execute("SELECT 1 FROM beliefs WHERE id = ?", (identifier,)).fetchone() is not None

            history = get_confidence_history(conn, identifier, is_belief)

            entity_type = "Belief" if is_belief else "Memory"
            print(f"{entity_type} #{identifier} Confidence History")
            print("=" * 70)

            if history:
                for entry in history:
                    print(f"  {format_timeline_entry(entry)}")
                print(f"\n({len(history)} changes)")
            else:
                print(f"No confidence changes recorded for {entity_type.lower()} #{identifier}")
        else:
            # Show general timeline
            project = flags.get("project")
            days = int(flags.get("days", 30))

            entries = get_timeline(conn, project=project, days=days)

            print(f"Timeline (last {days} days{f', project: {project}' if project else ''})")
            print("=" * 70)

            if entries:
                for entry in entries:
                    # Format entry with context
                    if entry['belief_statement']:
                        context = entry['belief_statement'][:40] + "..."
                    elif entry['memory_content']:
                        context = entry['memory_content'][:40] + "..."
                    else:
                        context = "Unknown"

                    print(f"  {format_timeline_entry(entry)}")
                    print(f"    Context: {context}")

                print(f"\n({len(entries)} changes)")

                # Show summary stats
                summary = get_timeline_summary(conn, days)
                print(f"\nSummary:")
                print(f"  Total changes: {summary['total_changes']}")
                print(f"  Increases: {summary['increases']} ↑")
                print(f"  Decreases: {summary['decreases']} ↓")
                print(f"  Avg delta: {summary['avg_confidence_delta']:+.3f}")
                if summary['by_source']:
                    by_source_str = ', '.join([f"{s['source_type']}({s['count']})" for s in summary['by_source']])
                print(f"  By source: {by_source_str}")
            else:
                print(f"No timeline entries in the last {days} days.")

        conn.close()

    elif cmd == "predictions":
        from .beliefs import list_predictions, expired_predictions
        conn = get_db()

        if "--open" in sys.argv:
            preds = list_predictions(conn, 'open')
            status_filter = 'open'
        elif "--confirmed" in sys.argv:
            preds = list_predictions(conn, 'confirmed')
            status_filter = 'confirmed'
        elif "--refuted" in sys.argv:
            preds = list_predictions(conn, 'refuted')
            status_filter = 'refuted'
        elif "--expired" in sys.argv:
            preds = expired_predictions(conn)
            status_filter = 'expired'
        else:
            preds = list_predictions(conn, 'all')
            status_filter = 'all'

        if preds:
            print(f"Predictions ({status_filter})")
            print("=" * 70)
            for p in preds:
                deadline_str = f" [deadline: {p['deadline']}]" if p['deadline'] else ""
                mem_ref = f" (based on #{p['memory_id']})" if p['memory_id'] else ""
                pred_preview = p['prediction'][:50] + "..." if len(p['prediction']) > 50 else p['prediction']
                print(f"  #{p['id']:>3} [{p['status']:<10}] {p['confidence']:.2f} {pred_preview}{deadline_str}{mem_ref}")
            print(f"\n({len(preds)} predictions)")
        else:
            print(f"No {status_filter} predictions.")

        conn.close()

    # Extended beliefs system commands
    elif cmd == "believe" and len(sys.argv) >= 3:
        from .beliefs_extended import add_belief
        flags, statement_parts = parse_flags(sys.argv, 2)
        statement = " ".join(statement_parts)

        conn = get_db()
        belief_id = add_belief(
            conn,
            statement,
            confidence=float(flags.get("confidence", 0.5)),
            category=flags.get("category", "general"),
            source=flags.get("source", "user"),
            memory_id=int(flags["memory"]) if "memory" in flags else None
        )
        conn.close()
        print(f"Created belief #{belief_id}")

    elif cmd == "evidence" and len(sys.argv) >= 4:
        from .beliefs_extended import add_evidence
        belief_id = int(sys.argv[2])
        memory_id = int(sys.argv[3])
        flags, _ = parse_flags(sys.argv, 4)

        direction = "supports" if "supports" in sys.argv else "contradicts"
        strength = float(flags.get("strength", 0.5))
        note = flags.get("note")

        conn = get_db()
        add_evidence(conn, belief_id, memory_id, direction, strength, note)
        conn.close()
        print(f"Added {direction} evidence to belief #{belief_id}")

    elif cmd == "belief-stats":
        from .beliefs_extended import belief_accuracy, strongest_beliefs, weakest_beliefs, most_revised
        conn = get_db()

        print("=== Belief System Statistics ===\n")

        # Prediction accuracy
        acc = belief_accuracy(conn)
        if acc['total_predictions'] > 0:
            print(f"Prediction Accuracy:")
            print(f"  Total: {acc['total_predictions']} ({acc['correct_count']} correct, {acc['incorrect_count']} incorrect)")
            print(f"  Accuracy: {acc['correct_percentage']:.1f}%")
            print(f"  Avg confidence (correct): {acc['avg_confidence_correct']:.2f}")
            print(f"  Avg confidence (incorrect): {acc['avg_confidence_incorrect']:.2f}")

            if acc['calibration']:
                print(f"\n  Calibration by confidence bucket:")
                for bucket, stats in acc['calibration'].items():
                    print(f"    {bucket}: {stats['accuracy']:.1%} actual vs {stats['expected']:.1%} expected ({stats['count']} predictions)")

        # Strongest beliefs
        print(f"\nStrongest Beliefs:")
        strong = strongest_beliefs(conn, 5)
        for b in strong:
            print(f"  #{b['id']} {b['confidence']:.2f} [{b['category']}] {b['statement'][:60]}")

        # Weakest beliefs
        print(f"\nWeakest Beliefs:")
        weak = weakest_beliefs(conn, 5)
        for b in weak:
            print(f"  #{b['id']} {b['confidence']:.2f} [{b['category']}] {b['statement'][:60]}")

        # Most revised (controversial)
        print(f"\nMost Revised (Controversial):")
        revised = most_revised(conn, 5)
        for b in revised:
            print(f"  #{b['id']} {b['revision_count']} revisions {b['confidence']:.2f} [{b['category']}] {b['statement'][:60]}")

        conn.close()

    elif cmd == "expired-predictions":
        from .beliefs_extended import check_expired_predictions
        conn = get_db()
        expired = check_expired_predictions(conn)
        conn.close()

        if expired:
            print(f"Found {len(expired)} expired predictions:\n")
            for p in expired:
                print(f"  #{p['id']} deadline: {p['deadline']}")
                print(f"    {p['prediction'][:80]}")
                print()
        else:
            print("No expired predictions.")

    elif cmd == "narrative" and len(sys.argv) >= 3:
        from .narrative import build_narrative, get_entity_stories, get_causal_chains
        entity_name = " ".join(sys.argv[2:])
        flags, name_parts = parse_flags(sys.argv, 2)
        if name_parts:
            entity_name = " ".join(name_parts)

        conn = get_db()
        result = build_narrative(conn, entity_name, max_depth=int(flags.get("depth", 3)))

        if result['entity']:
            print(result['narrative'])

            # Show causal chains
            chains = get_causal_chains(conn, entity_name)
            if chains:
                print(f"\nCausal chains ({len(chains)}):")
                for chain in chains[:5]:
                    print(f"  {' → '.join(chain)}")
        else:
            print(f"Entity '{entity_name}' not found.")
            # Show entities with richest stories
            stories = get_entity_stories(conn, 5)
            if stories:
                print("\nEntities with narratives:")
                for s in stories:
                    print(f"  {s['name']} ({s['type']}) — {s['rel_count']} relationships, {s['mem_count']} memories")
        conn.close()

    elif cmd == "meta":
        from .meta_learning import get_meta_stats, apply_learned_weights
        conn = get_db()

        if "--apply" in sys.argv:
            result = apply_learned_weights(conn)
            if result['applied']:
                print("✓ Search weights updated:")
                print(f"  Keyword: {result['old_weights']['keyword_weight']:.2f} → {result['new_weights']['keyword_weight']:.2f}")
                print(f"  Semantic: {result['old_weights']['semantic_weight']:.2f} → {result['new_weights']['semantic_weight']:.2f}")
                print(f"  Reason: {result['recommendation']}")
            else:
                print(f"No changes applied: {result['reason']}")
        else:
            stats = get_meta_stats(conn)
            print("Meta-Learning Report")
            print("=" * 70)
            print(f"\nCurrent weights:")
            for k, v in stats['current_weights'].items():
                print(f"  {k}: {v:.2f}")

            eff = stats['effectiveness_30d']
            print(f"\nLast 30 days ({eff['total_searches']} searches):")
            print(f"  Keyword effectiveness: {eff['keyword_effectiveness']:.1%}")
            print(f"  Semantic effectiveness: {eff['semantic_effectiveness']:.1%}")
            print(f"  Overall hit rate: {eff['overall_hit_rate']:.1%}")
            print(f"  Recommendation: {eff['recommendation']}")

            if eff['recommendation'] not in ('balanced', 'insufficient_data'):
                print(f"\nSuggested weights:")
                for k, v in eff['suggested_weights'].items():
                    curr = stats['current_weights'].get(k, 0)
                    delta = v - curr
                    arrow = "↑" if delta > 0 else "↓" if delta < 0 else "="
                    print(f"  {k}: {v:.2f} ({arrow}{abs(delta):.2f})")
                print(f"\nRun 'memory-tool meta --apply' to apply suggested weights")

            print(f"\nWeight changes: {stats['weight_changes']} total")
        conn.close()

    elif cmd == "identity":
        from .identity import discover_traits, get_identity, save_identity_snapshot, compare_identity_snapshots
        conn = get_db()

        if "--discover" in sys.argv or "--refresh" in sys.argv:
            print("Discovering traits from memories...\n")
            traits = discover_traits(conn)
            save_identity_snapshot(conn)

            if traits:
                print(f"Found {len(traits)} traits:\n")
                for t in traits:
                    bar = "█" * int(t['confidence'] * 10) + "░" * (10 - int(t['confidence'] * 10))
                    print(f"  {bar} {t['confidence']:.0%}  {t['description']}")
                    print(f"         Evidence: {t['evidence_count']} for, {t['counter_evidence']} against")
            else:
                print("No traits discovered. Add more memories first.")

        elif "--evolution" in sys.argv:
            result = compare_identity_snapshots(conn)
            if result['has_comparison']:
                print(f"Identity Evolution: {result['previous_date'][:10]} → {result['current_date'][:10]}")
                print("=" * 70)

                if result['new_traits']:
                    print(f"\nNew traits ({len(result['new_traits'])}):")
                    for t in result['new_traits']:
                        print(f"  + {t['trait_name']} ({t['confidence']:.0%})")

                if result['removed_traits']:
                    print(f"\nRemoved traits ({len(result['removed_traits'])}):")
                    for t in result['removed_traits']:
                        print(f"  - {t['trait_name']}")

                if result['changed']:
                    print(f"\nConfidence changes:")
                    for c in result['changed']:
                        arrow = "↑" if c['delta'] > 0 else "↓"
                        print(f"  {arrow} {c['trait_name']}: {c['old_confidence']:.0%} → {c['new_confidence']:.0%}")

                if not result['new_traits'] and not result['removed_traits'] and not result['changed']:
                    print("\nNo significant changes between snapshots.")
            else:
                print(result['message'])
                print("Run 'memory-tool identity --discover' to create first snapshot.")

        else:
            # Show current identity
            identity = get_identity(conn)

            if identity['traits']:
                print("Identity Profile")
                print("=" * 70)
                print(f"\n{identity['summary']}")
                print(f"\nTotal: {identity['total_traits']} traits, {identity['total_evidence']} evidence points")
                print(f"  Strong: {len(identity['strong'])} | Moderate: {len(identity['moderate'])} | Weak: {len(identity['weak'])}")
            else:
                print("No identity profile yet.")
                print("Run 'memory-tool identity --discover' to build profile from memories.")

        conn.close()

    elif cmd == "session-log":
        from pathlib import Path

        SESSION_LOG = Path("/tmp/ai-iq-session-log.jsonl")

        if not SESSION_LOG.exists():
            print("No session log found. Hook not yet active or no tools executed.")
            print(f"To enable, install hook: /root/ai-iq/hooks/session-logger.mjs")
            sys.exit(0)

        # Read and display session log
        flags, _ = parse_flags(sys.argv, 2)
        limit = int(flags.get("limit", 50))  # Default last 50 entries
        show_errors_only = flags.get("errors", False)

        entries = []
        with open(SESSION_LOG, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    entries.append(entry)
                except json.JSONDecodeError:
                    continue

        # Filter if errors-only mode
        if show_errors_only:
            entries = [e for e in entries if e.get('tool') == 'Bash' and e.get('exit_code') != 0]

        # Show last N entries
        recent = entries[-limit:]

        print(f"Session log ({len(recent)} of {len(entries)} total entries):")
        print()

        for e in recent:
            ts = e.get('timestamp', '')[:19]  # Trim milliseconds
            tool = e.get('tool', 'Unknown')

            if tool == 'Bash':
                cmd = e.get('input', '')
                exit_code = e.get('exit_code', '?')
                status = "✓" if exit_code == 0 else "✗"
                print(f"{ts} [{tool}] {status} {cmd}")
                if exit_code != 0:
                    preview = e.get('output_preview', '')
                    if preview:
                        print(f"    Error: {preview}")
            elif tool in ('Read', 'Edit', 'Write'):
                file_path = e.get('file_path', '')
                action = e.get('action', '')
                print(f"{ts} [{tool}] {action} {file_path}")
            elif tool in ('Glob', 'Grep'):
                pattern = e.get('pattern', '')
                preview = e.get('output_preview', '')
                print(f"{ts} [{tool}] {pattern} → {preview}")
            else:
                inp = e.get('input', '')[:50]
                preview = e.get('output_preview', '')[:50]
                print(f"{ts} [{tool}] {inp} → {preview}")

        print()
        print(f"Use --limit N to show more, --errors to show only failures")

    elif cmd == "mode":
        from .modes import get_mode, set_mode, list_modes

        if len(sys.argv) == 2:
            # Show current mode
            current = get_mode()
            print(f"Current mode: {current}")
            print("\nRun 'memory-tool mode list' to see all modes")
            print("Run 'memory-tool mode <name>' to switch")

        elif sys.argv[2] == "list":
            # List all modes
            list_modes()

        else:
            # Set mode
            mode_name = sys.argv[2]
            if set_mode(mode_name):
                print(f"✅ Switched to mode: {mode_name}")
            else:
                print(f"❌ Failed to set mode. Valid modes: default, dev, ops, research, monitor")
                sys.exit(1)

    elif cmd in ("help", "--help", "-h"):
        print_help()

    else:
        print(f"Unknown command: {cmd}")
        print_help()
        sys.exit(1)

