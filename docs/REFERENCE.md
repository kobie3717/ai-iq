# AI-IQ Complete Reference

This document contains the full feature documentation moved from the main README.

## Table of Contents
- [Features Overview](#features-overview)
- [Belief System](#belief-system)
- [Knowledge Graph](#knowledge-graph)
- [Dream Mode](#dream-mode)
- [Self-Learning Feedback](#self-learning-feedback)
- [Identity Layer](#identity-layer)
- [Narrative Memory](#narrative-memory)
- [Integrations](#integrations)
- [Command Reference](#command-reference)
- [Architecture Details](#architecture-details)
- [Claude Code Plugin](#claude-code-plugin)

## Features Overview

### Core Memory Operations
- **Add/Update/Delete** - Standard CRUD with content deduplication
- **Hybrid Search** - RRF fusion of keyword (FTS5) + semantic (vector) + graph traversal
- **Categories** - `project`, `decision`, `preference`, `error`, `learning`, `pending`, `architecture`, `workflow`, `contact`
- **Tags & Metadata** - Auto-tagging from content keywords, manual tags, priorities (0-10)
- **Topic Keys** - Upsert-style identifiers for stable updates without duplicates
- **Expiry & Decay** - Auto-stale after 30d (pending) or 90d (general), priority decay after 60d

## Belief System (Unique to AI-IQ)

Track what your AI thinks it knows with confidence scores (0.01-0.99). When predictions resolve, related beliefs strengthen or weaken automatically via Bayesian-style learning.

- **Confidence Scoring** - Beliefs track confidence from 0.01 to 0.99
- **Prediction Engine** - Make testable predictions with deadlines and expected outcomes
- **Bayesian Updates** - When predictions resolve (confirmed/refuted), related beliefs adjust confidence automatically
- **Confidence Propagation** - Updates flow through memory relationships via causal graph
- **Belief Queries** - Find weak/strong/conflicting beliefs, track open/expired predictions

```bash
memory-tool believe "TypeScript reduces bugs vs JavaScript" --confidence 0.75
memory-tool predict "Next rewrite will have 30% fewer runtime errors" --based-on 1 --deadline 2026-06-01
memory-tool resolve 1 --confirmed "Runtime errors down 42%"  # Belief → 0.85
memory-tool beliefs --weak                                    # Show lowest confidence beliefs
memory-tool predictions --open                                # Show active predictions
```

## Knowledge Graph

Build relationships between entities and extract context via spreading activation.

- **Entities** - `person`, `project`, `org`, `feature`, `concept`, `tool`, `service`
- **Relationships** - `knows`, `works_on`, `owns`, `depends_on`, `built_by`, `uses`, `related_to`, `PREVENTS`, `RESOLVES`, `LEADS_TO`, `REQUIRES` (causal edges)
- **Facts** - Key-value metadata on entities with history tracking
- **Spreading Activation** - Find related context by traversing relationships with decay
- **Auto-Linking** - Link memories to entities by name/keyword matching

```bash
memory-tool graph add project WhatsAuction "Real-time auction platform"
memory-tool graph add tool Redis "In-memory cache"
memory-tool graph rel WhatsAuction uses Redis "For session storage"
memory-tool graph rel WhatsAuction REQUIRES Redis "Cache must be up before app starts"
memory-tool graph fact Redis version "7.2.4"
memory-tool graph spread WhatsAuction --depth 2    # Find all related context
memory-tool graph auto-link                        # Link existing memories to entities
```

## Dream Mode (Unique to AI-IQ)

Autonomous consolidation inspired by REM sleep in biological memory.

- **Duplicate Detection** - Finds 85-95% similar memories, auto-merges with provenance
- **Reconsolidation** - Strengthens frequently-accessed patterns, weakens unused ones
- **Contradiction Detection** - Warns on >80% similar memories with negation patterns (but doesn't block)
- **Metadata Normalization** - Standardizes dates, project names, tags
- **Decay Processing** - Flags stale memories, reduces priority, expires old TODOs

```bash
memory-tool dream
# Output:
#   Consolidated 5 duplicates (kept newer, marked old as superseded)
#   Detected 2 potential contradictions (flagged for review)
#   Normalized 8 dates to ISO format
#   Expired 3 pending items past deadline
#   Strengthened 12 high-access memories (+1 priority)
#   Weakened 4 low-access memories (-1 priority)
```

## Self-Learning Feedback Loop (Unique to AI-IQ)

Meta-learning that improves search quality over time.

- **Outcome Tracking** - Every search logs which results you actually use
- **Effectiveness Scoring** - Calculates keyword vs semantic hit rates
- **Weight Tuning** - Auto-adjusts RRF fusion weights based on what works
- **Promotion/Demotion** - High-value memories get priority boost, noise gets flagged

```bash
memory-tool search-quality          # View effectiveness metrics
memory-tool hot                     # Show most accessed memories (immune to decay)
memory-tool feedback <search_id> <used_memory_ids>  # Manual feedback logging
```

## Identity Layer (Unique to AI-IQ)

Discovers behavioral traits from memory patterns.

- **Trait Detection** - Mines decisions, errors, beliefs for tendencies (e.g., `prefers_docker`, `ships_fast`, `tests_first`)
- **Confidence Tracking** - Each trait has evidence count and confidence score
- **Evolution Tracking** - Snapshots show how traits change over time
- **Pattern Recognition** - Detects anti-patterns and conflicts

```bash
memory-tool identity --discover
memory-tool identity --snapshot "After WhatsAuction rewrite"
memory-tool identity --evolution prefers_docker    # Show trait changes over time
```

## Narrative Memory (Unique to AI-IQ)

Builds cause-effect stories from causal graph edges.

- **Causal Chains** - Walks `LEADS_TO`, `PREVENTS`, `RESOLVES`, `REQUIRES` edges
- **Chronological Stories** - Sorts by timestamp to show progression
- **Linked Context** - Includes related memories for full narrative
- **Deduplication** - Removes redundant events for clean stories

```bash
memory-tool narrative WhatsAuction
```

## Integrations

**Claude Code Hooks** - Auto-captures errors, generates session snapshots, logs feedback

**OpenClaw Bridge** - Bidirectional sync with OpenClaw's file-based memory:
```bash
memory-tool sync          # Two-way sync
memory-tool sync-to       # AI-IQ → OpenClaw
memory-tool sync-from     # OpenClaw → AI-IQ
```

**Session Tracking** - Structured workflows with steps and outcomes:
```bash
memory-tool run start "Fix authentication bug" --agent claude --project MyApp
memory-tool run step 1 "Identified issue in JWT validation"
memory-tool run complete 1 "Fixed, all tests passing"
memory-tool run list --status completed
```

## Command Reference

### Core Operations
| Command | Description |
|---------|-------------|
| `memory-tool add <category> "<content>" [options]` | Create memory with optional --project, --tags, --priority, --expires, --key |
| `memory-tool update <id> "<new content>"` | Update memory (auto re-embeds for semantic search) |
| `memory-tool delete <id>` | Soft delete (recoverable) |
| `memory-tool get <id>` | Full detail view with relationships |
| `memory-tool list [--project/--category/--tag/--stale/--expired]` | Filter and list memories |

### Search & Discovery
| Command | Description |
|---------|-------------|
| `memory-tool search "<query>" [--full/--semantic/--keyword]` | Hybrid search (default), verbose (--full), mode-specific |
| `memory-tool conflicts` | Find 50-85% similar memories (potential duplicates) |
| `memory-tool merge <id1> <id2>` | Merge similar memories (keeps newer) |
| `memory-tool supersede <old> <new>` | Mark old as superseded by new |
| `memory-tool pending` | Show TODO items |
| `memory-tool hot` | Most accessed memories (access_count >= 5 = immune to decay) |
| `memory-tool next` | Smart suggestions: what needs attention now |

### Beliefs & Predictions
| Command | Description |
|---------|-------------|
| `memory-tool believe "<statement>" --confidence 0.7` | Create belief with confidence score |
| `memory-tool predict "<prediction>" --based-on <id> --deadline YYYY-MM-DD` | Make testable prediction |
| `memory-tool resolve <pred_id> --confirmed/--refuted "<outcome>"` | Resolve prediction (auto-updates belief confidence) |
| `memory-tool beliefs [--weak/--strong/--conflicts]` | List beliefs by confidence |
| `memory-tool predictions [--open/--confirmed/--refuted/--expired]` | Filter predictions by status |

### Knowledge Graph
| Command | Description |
|---------|-------------|
| `memory-tool graph add <type> <name> [summary]` | Create entity (person/project/org/feature/concept/tool/service) |
| `memory-tool graph rel <from> <rel_type> <to> [note]` | Add relationship (uses/depends_on/PREVENTS/RESOLVES/LEADS_TO/REQUIRES) |
| `memory-tool graph fact <entity> <key> <value>` | Set entity metadata (tracks history) |
| `memory-tool graph get <name>` | Entity details with facts + relationships + linked memories |
| `memory-tool graph spread <name> [depth]` | Spreading activation (find related context) |
| `memory-tool graph auto-link` | Auto-link all memories to entities by keyword matching |

### Identity & Narrative
| Command | Description |
|---------|-------------|
| `memory-tool identity --discover` | Detect behavioral traits from memory patterns |
| `memory-tool identity --snapshot "<desc>"` | Save current trait snapshot |
| `memory-tool identity --evolution <trait>` | Show how trait changed over time |
| `memory-tool narrative <entity>` | Build cause-effect story from causal graph edges |

### Meta-Learning & Feedback
| Command | Description |
|---------|-------------|
| `memory-tool search-quality` | View keyword/semantic effectiveness metrics |
| `memory-tool feedback <search_id> <used_ids>` | Manual feedback logging (which results were useful) |
| `memory-tool tune-weights` | Re-calculate RRF fusion weights from feedback data |

### Session Management
| Command | Description |
|---------|-------------|
| `memory-tool snapshot "<summary>" [--project X]` | Manual session snapshot |
| `memory-tool auto-snapshot` | Auto-detect changes from git/filesystem |
| `memory-tool run start "<task>" --agent <name> --project <name>` | Start tracked workflow |
| `memory-tool run step <id> "<description>"` | Add step to active run |
| `memory-tool run complete/fail/cancel <id> "<outcome>"` | Finish run |
| `memory-tool run list [--status running/completed/failed]` | List runs with filters |

### Maintenance
| Command | Description |
|---------|-------------|
| `memory-tool dream` | Consolidate duplicates, resolve conflicts, normalize metadata, run decay |
| `memory-tool decay` | Flag stale memories, reduce priorities, expire old TODOs |
| `memory-tool stale` | Review stale memories |
| `memory-tool gc [days]` | Garbage collect inactive memories (default: 180 days) |
| `memory-tool reindex` | Rebuild vector embeddings for all memories |
| `memory-tool backup` | Manual backup to ~/.claude/backups/ |
| `memory-tool restore <file>` | Restore from backup |
| `memory-tool stats` | Full statistics (memories + vectors + graph + beliefs + runs) |

### Cross-Tool Sync
| Command | Description |
|---------|-------------|
| `memory-tool sync` | Bidirectional sync with OpenClaw |
| `memory-tool sync-to` | Export to OpenClaw workspace format |
| `memory-tool sync-from` | Import from OpenClaw workspace |

## Architecture Details

**Inspired by biological memory principles:**
- **Hippocampus → Neocortex** - Short-term memories (recent sessions) consolidate into long-term via dream mode
- **REM Sleep Consolidation** - Dream mode strengthens important patterns, prunes noise
- **Spreading Activation** - Graph traversal mimics how human memory retrieves related concepts
- **Confidence Updates** - Bayesian-style learning from prediction outcomes

**Database schema (SQLite 3.37+):**
- `memories` - Core storage with FTS5 index + vector embeddings (384-dim all-MiniLM-L6-v2)
- `memory_relations` - Bidirectional links between memories
- `graph_entities` - Knowledge graph nodes (people, projects, tools, concepts)
- `graph_relationships` - Causal edges (PREVENTS, RESOLVES, LEADS_TO, REQUIRES) + semantic edges (uses, depends_on, etc.)
- `graph_facts` - Entity metadata with history tracking
- `beliefs` - Confidence-scored statements with Bayesian update tracking
- `predictions` - Testable hypotheses with deadlines and resolution tracking
- `identity_traits` - Behavioral patterns with evidence counts
- `runs` - Workflow/session tracking with steps and timing
- `search_feedback` - Meta-learning data for weight tuning

**Hybrid Search (RRF fusion with k=60):**
1. Keyword search via FTS5 (fast, exact matches)
2. Semantic search via sqlite-vec embeddings (conceptual similarity)
3. Graph traversal via spreading activation (relationship-based)
4. Recency/confidence/access bonuses
5. Meta-learned weights adjust fusion based on effectiveness

## Claude Code Plugin

AI-IQ provides a ready-to-use Claude Code plugin with automatic error capture, session snapshots, and intelligent memory management.

### Quick Install

```bash
# Install AI-IQ
pip install ai-iq

# Run the plugin installer
cd /path/to/ai-iq
bash hooks/claude-code/install.sh
```

### What Gets Automated

Once installed, the plugin automatically:

- **PostToolUse hook**: Auto-captures failed Bash commands as error memories
- **Stop hook**: Auto-snapshots session (detects git/file changes), runs decay, exports MEMORY.md, daily backups
- **SessionStart hook**: Logs session start for timeline tracking
- **Daily cron** (optional): Dream consolidation, garbage collection, backups at 3:17 AM

For detailed setup and troubleshooting, see [hooks/claude-code/PLUGIN_README.md](../hooks/claude-code/PLUGIN_README.md)

## Comparison with Other Systems

| Feature | AI-IQ | Mem0 | Zep/Graphiti | Letta | Claude Auto Dream |
|---------|-------|------|--------------|-------|-------------------|
| **Portable single file** | ✅ SQLite | ❌ Cloud DB | ❌ Cloud DB | ✅ Filesystem | ✅ SQLite |
| **Causal beliefs with confidence** | ✅ Full system | ❌ None | ❌ None | ❌ None | ❌ None |
| **Prediction engine + resolution** | ✅ Bayesian updates | ❌ None | ❌ None | ❌ None | ❌ None |
| **Dream consolidation** | ✅ Autonomous REM-like | ❌ None | ❌ None | ❌ None | ⚠️ Shallow merge |
| **Identity layer (behavioral traits)** | ✅ Auto-discovers | ❌ None | ❌ None | ❌ None | ❌ None |
| **Narrative memory (causal chains)** | ✅ LEADS_TO/PREVENTS edges | ❌ None | ⚠️ Temporal only | ❌ None | ❌ None |
| **Meta-learning search tuning** | ✅ Feedback loop | ❌ Static | ❌ Static | ❌ Static | ❌ None |
| **Coding-specific hooks** | ✅ PostToolUse/Stop | ❌ Generic | ❌ Generic | ❌ Generic | ✅ But locked to Claude |
| **No cloud dependency** | ✅ 100% local | ❌ Cloud SaaS | ❌ Cloud SaaS | ✅ Local | ✅ Local |
| **No vendor lock-in** | ✅ Standard SQL | ❌ Proprietary API | ❌ Proprietary | ✅ Open format | ⚠️ Claude ecosystem only |
| **Knowledge graph** | ✅ Entities + relationships + facts | ✅ Strong | ✅ Very strong | ❌ None | ❌ None |
| **Hybrid search (keyword + semantic)** | ✅ RRF fusion | ✅ Yes | ✅ Yes | ⚠️ Tiered only | ❌ Keyword only |
| **Vector embeddings** | ✅ Optional (384-dim) | ✅ Required | ✅ Required | ✅ Required | ❌ None |
| **Zero dependencies** | ✅ Core works bare | ❌ Heavy stack | ❌ Heavy stack | ❌ Heavy stack | ✅ SQLite only |

## Real-World Usage

**Production stats from 6 months of daily use:**
- 220+ active memories across 7 projects
- 32 entities, 45 relationships in knowledge graph
- 109 vector embeddings for semantic search
- 18 beliefs with confidence tracking
- 12 predictions resolved (9 confirmed, 3 refuted)
- 24 identity traits discovered
- 697 duplicates consolidated via dream mode
- Zero data loss, zero corruption
