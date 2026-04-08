# Reflexion Self-Improvement System

AI-IQ v5.10.0 includes a Reflexion-style self-improvement system that helps agents learn from past mistakes and build on successful patterns.

## What is Reflexion?

Reflexion is a technique where an agent writes structured verbal reflections after completing tasks. These reflections capture:
- What worked well
- What failed or didn't work
- What to do differently next time

The reflection is stored as memory and retrieved before similar future tasks, preventing repeated mistakes. Research shows 20-40% improvement on agent tasks.

## Commands

### `memory-tool reflect`

Add a reflection after completing a task.

**Interactive mode:**
```bash
memory-tool reflect "Fixed nginx configuration"
```

You'll be prompted for:
- Outcome (success/partial/failure)
- What worked well
- What failed or didn't work
- What to do differently next time
- Project (optional)

**Batch mode:**
```bash
memory-tool reflect "Fixed WhatsHub nginx config" \
  --outcome partial \
  --worked "Checking nginx syntax first" \
  --failed "Forgot to reload after edit" \
  --next "Always run nginx -t && systemctl reload nginx" \
  --project WhatsHub
```

### `memory-tool reflect-load`

Load relevant past reflections before starting a task.

```bash
memory-tool reflect-load "nginx configuration"
```

Returns top 3 most relevant reflections showing:
- What failed before
- What worked
- What to do differently

**Example workflow:**
```bash
# Before making nginx changes
memory-tool reflect-load "nginx"

# Make your changes...

# After completing the task
memory-tool reflect "Updated nginx SSL config" \
  --outcome success \
  --worked "Used reflect-load to check past mistakes" \
  --failed "None" \
  --next "Keep using reflect-load before config changes"
```

### `memory-tool lessons`

Show all stored reflections grouped by task type with statistics.

```bash
memory-tool lessons
```

Output shows:
- Reflections grouped by task type (debugging, deployment, configuration, etc.)
- Success/partial/failure counts per task type
- Recent reflections for each type
- **Pattern detection** - highlights task types with high failure rates

## How It Works

### Storage

Reflections are stored as `learning` category memories with:
- **Tag**: `reflection` + outcome (success/partial/failure) + auto-detected type
- **Wing**: `reflections` (namespace for easy filtering)
- **Room**: task type (configuration, deployment, debugging, etc.)
- **Priority**: 1 for failures (higher priority), 0 for success/partial

### Task Type Auto-Detection

The system auto-detects task types from keywords:
- `nginx`, `apache`, `config` → configuration
- `deploy`, `release`, `push` → deployment
- `bug`, `fix`, `error` → debugging
- `test`, `pytest`, `jest` → testing
- `database`, `sql`, `migration` → database
- `api`, `endpoint`, `route` → api
- Everything else → general

### Retrieval

When you run `reflect-load`, the system:
1. Uses hybrid search (FTS + semantic) to find relevant past reflections
2. Filters to `wing=reflections` only
3. Returns top 3 most relevant matches
4. Parses structured fields for display

### Pattern Detection

The `lessons` command identifies patterns:
- Task types with ≥50% failure rate are flagged
- Requires at least 3 reflections in that category
- Helps identify areas needing skill development

## Best Practices

1. **Be specific in task summaries**: "Fixed nginx SSL config" > "Fixed config"
2. **Reflect on failures immediately**: Details are fresh in your mind
3. **Use reflect-load before starting tasks**: Especially for repeated task types
4. **Review lessons periodically**: Run `memory-tool lessons` weekly
5. **Focus on actionable next steps**: "Always backup first" > "Be more careful"

## Example Session

```bash
# Starting a deployment
$ memory-tool reflect-load "deploy to production"

📚 Past Reflections for: deploy to production
======================================================================

1. ❌ Deployed API without testing
   ID: #1523 | Created: 2026-03-15
   ✗ What failed: Skipped staging environment
   → Next time: ALWAYS deploy to staging first

======================================================================

# Deploy following the lesson
$ # ... deployment steps with staging first ...

# Record the successful deployment
$ memory-tool reflect "Deployed auth API to production" \
  --outcome success \
  --worked "Tested in staging first, used blue-green deployment" \
  --failed "None" \
  --next "Keep using blue-green for zero-downtime deploys" \
  --project FlashVault

✅ Reflection #1927 stored
```

## Integration with Other Systems

Reflections integrate seamlessly with:

- **FSRS decay**: Accessed reflections stay fresh, unused ones decay
- **Importance scoring**: Failure reflections get higher importance
- **Search**: Hybrid search finds reflections across projects
- **Graph**: Can link reflections to entities/projects
- **Focus mode**: Include reflections in context briefs

## Hook System (Optional)

A lightweight hook is provided at `hooks/post-task/reflect-hook.sh` that logs commands to `/tmp/reflect-queue.jsonl`.

To enable automatic reflection suggestions:
```bash
# In your .bashrc or shell config
trap '/path/to/ai-memory-sqlite/hooks/post-task/reflect-hook.sh "$BASH_COMMAND" "$?"' DEBUG
```

Note: This is optional and experimental. Manual reflection via `memory-tool reflect` is the primary workflow.

## Research Background

Based on the Reflexion paper by Shinn et al. (2023):
- Verbal reinforcement helps agents learn from mistakes
- Self-reflection improves task success rates by 20-40%
- Structured reflection (what worked/failed/next) > unstructured notes
- Retrieval before similar tasks prevents repeated failures

## Version History

- v5.10.0 (2026-04-08): Initial Reflexion implementation
  - `reflect`, `reflect-load`, `lessons` commands
  - Wing/room organization for reflections
  - Pattern detection for high-failure task types
  - Auto task type detection
