# Focus Command

The `focus` command provides an instant context brief on any topic by pulling together everything from the memory system in one view.

## Usage

```bash
# Compact view (default) - shows top 5 memories
memory-tool focus <topic>

# Full detail view - shows top 10 memories with complete content
memory-tool focus <topic> --full
```

## What It Shows

The focus command compiles the following sections:

### 1. Key Memories
- **Compact mode**: Top 5 matching memories with preview
- **Full mode**: Top 10 matching memories with complete content
- Uses hybrid search (FTS + semantic) for best relevance

### 2. Knowledge Graph
- Entity information (if exists)
- Facts with confidence scores
- Relationships (incoming and outgoing)
- Linked memories
- Related entities via spreading activation (compact mode only)

### 3. Pending Items
- TODOs and pending tasks mentioning the topic
- Shows up to 10 items

### 4. Beliefs
- Beliefs mentioning the topic
- Sorted by confidence
- Shows up to 10 beliefs

### 5. Predictions
- Open/pending predictions mentioning the topic
- Includes confidence and deadline
- Shows up to 10 predictions

### 6. Suggested Actions
- Stale memories to review
- Expired predictions to resolve
- Potential conflicts to merge

## Examples

```bash
# Get context on a project
memory-tool focus "whatsauction"

# Get context on a technical topic with full details
memory-tool focus "docker" --full

# Get context on a contact
memory-tool focus "bruce esser"

# Get context on a technology
memory-tool focus "redis"

# Get context on a process
memory-tool focus "deployment"
```

## Output Format

The output is formatted as clean Markdown with:
- Clear section headers
- Memory IDs for easy reference
- Project tags where applicable
- Confidence scores for beliefs/predictions
- Actionable suggestions with commands

## Integration with Other Commands

The focus command references other memory-tool commands:
- `memory-tool search "<topic>"` - Deep dive into memories
- `memory-tool get <id>` - View full memory detail
- `memory-tool graph get <entity>` - View graph entity detail
- `memory-tool conflicts` - Review potential duplicates
- `memory-tool pending` - View all pending items
- `memory-tool beliefs` - View all beliefs
- `memory-tool predictions` - View all predictions

## Use Cases

1. **Project Context**: `memory-tool focus "project-name"` - Get instant project overview
2. **Technology Review**: `memory-tool focus "redis"` - Review all knowledge about a tech
3. **Contact Recap**: `memory-tool focus "contact-name"` - Get all info about a person
4. **Decision History**: `memory-tool focus "decision-topic"` - Review past decisions
5. **Learning Check**: `memory-tool focus "learning-topic"` - See what you've learned

## Implementation

- Location: `/root/ai-iq/memory_tool/focus.py`
- Tests: `/root/ai-iq/tests/test_focus.py`
- CLI Integration: `/root/ai-iq/memory_tool/cli.py`

## Design Philosophy

The focus command follows the "progressive disclosure" principle:
- **Compact mode** (default): Quick overview, easy to scan
- **Full mode**: Detailed view for deep work
- **Sections only shown if data exists**: No clutter
- **Actionable suggestions**: Guides next steps
- **Clean markdown**: Easy to read and copy
