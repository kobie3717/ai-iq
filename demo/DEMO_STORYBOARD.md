# AI-IQ Demo Storyboard

Visual guide to what users will see in the asciinema demo.

---

## Frame 1: Introduction (0-3 seconds)
```
# 🦀 AI-IQ: SQLite for AI memory
# pip install ai-iq

$ _
```
**Purpose**: Hook attention, show installation simplicity

---

## Frame 2: Adding Memories (3-12 seconds)
```
# 💾 Store memories with context

$ memory-tool add project "WhatsApp auction platform launched - 50 users in first week" --tags launch,growth
✓ Added memory #1

$ memory-tool add decision "Switched from REST to WebSocket for real-time bidding - 3x faster" --tags architecture
✓ Added memory #2

$ memory-tool add learning "PostgreSQL NOTIFY/LISTEN better than polling for auction events" --tags database,performance
✓ Added memory #3

$ memory-tool add error "Memory leak in WebSocket handler - connections not cleaned up on disconnect" --tags bug,websocket
✓ Added memory #4
```
**Purpose**: Show variety of memory types (project, decision, learning, error)

---

## Frame 3: Hybrid Search (12-18 seconds)
```
# 🔍 Hybrid search finds connections across memories

$ memory-tool search "real-time performance"

┌─────┬───────────────────────────────────────────────────────────────────────┐
│  #2 │ Switched from REST to WebSocket for real-time bidding - 3x faster    │
│     │ Tags: architecture                                                     │
├─────┼───────────────────────────────────────────────────────────────────────┤
│  #3 │ PostgreSQL NOTIFY/LISTEN better than polling for auction events       │
│     │ Tags: database, performance                                            │
└─────┴───────────────────────────────────────────────────────────────────────┘

Found 2 memories (keyword + semantic + graph fusion)
```
**Purpose**: Demonstrate intelligent search across unrelated memories

---

## Frame 4: Knowledge Graph (18-28 seconds)
```
# 🕸️  Build knowledge graphs

$ memory-tool graph add project AuctionApp
✓ Entity 'AuctionApp' added

$ memory-tool graph add tool WebSocket
✓ Entity 'WebSocket' added

$ memory-tool graph rel AuctionApp uses WebSocket
✓ Relationship created: AuctionApp → uses → WebSocket

$ memory-tool graph get AuctionApp

Entity: AuctionApp (project)
├─ uses → WebSocket
├─ Related memories: 4
└─ Created: 2026-04-02
```
**Purpose**: Show structured knowledge beyond flat text

---

## Frame 5: Beliefs (28-33 seconds)
```
# 🎯 Track beliefs with confidence

$ memory-tool believe "WebSocket scales to 10k concurrent users" --confidence 0.7
✓ Belief added with confidence 70%

$ memory-tool beliefs

┌────┬──────────────────────────────────────────────────────┬────────────┐
│ ID │ Belief                                                │ Confidence │
├────┼──────────────────────────────────────────────────────┼────────────┤
│  5 │ WebSocket scales to 10k concurrent users             │     70%    │
└────┴──────────────────────────────────────────────────────┴────────────┘
```
**Purpose**: Show unique feature (beliefs with uncertainty tracking)

---

## Frame 6: System Stats (33-42 seconds)
```
# 📊 Full system stats

$ memory-tool stats

╔════════════════════════════════════════════════════════════════╗
║                      AI-IQ Memory Stats                        ║
╠════════════════════════════════════════════════════════════════╣
║ Total Memories:                     5                          ║
║ Active:                             5                          ║
║ Stale:                              0                          ║
║ Expired:                            0                          ║
║                                                                ║
║ Vector Embeddings:                  5                          ║
║ Graph Entities:                     2                          ║
║ Graph Relationships:                1                          ║
║ Beliefs:                            1                          ║
║ Predictions:                        0                          ║
║                                                                ║
║ Categories:                                                    ║
║   project:    1    decision:   1    learning:  1              ║
║   error:      1    general:    1                              ║
║                                                                ║
║ Database Size:                  24.5 KB                        ║
║ Last Backup:                    never                          ║
╚════════════════════════════════════════════════════════════════╝
```
**Purpose**: Show comprehensive system overview, emphasize lightweight footprint

---

## Frame 7: Call-to-Action (42-45 seconds)
```
# ✨ Install: pip install ai-iq
# 📚 Docs: https://github.com/kobie3717/ai-iq

$ _
```
**Purpose**: Drive conversion with clear next steps

---

## Key Visual Elements

1. **Emoji headers** - Quick visual navigation (💾🔍🕸️🎯📊)
2. **Box drawing** - Clean table layouts for scan-ability
3. **Progress indicators** - ✓ checkmarks for successful operations
4. **Typing animation** - Realistic terminal feel (0.03s/char)
5. **Consistent $ prompts** - Professional CLI aesthetic

## Color Scheme (Monokai theme)
- Background: Dark gray/black
- Text: Light gray/white
- Accent: Green (success), Blue (links), Orange (warnings)
- Emoji: Full color for visual pops

## Timing Budget
- Intro: 3s
- Add memories: 9s (4 commands @ 2.25s each)
- Search: 6s (command + results)
- Graph: 10s (4 commands @ 2.5s each)
- Beliefs: 5s (2 commands @ 2.5s each)
- Stats: 9s (command + read time)
- Outro: 3s

**Total: 45 seconds** (plays at 1.5x = 30s on website)

## Success Metrics
- ✓ Shows all 5 key differentiators vs competitors
- ✓ Demonstrates actual working CLI (not mocked)
- ✓ Under 45 seconds (attention span sweet spot)
- ✓ Clear installation path (pip install ai-iq)
- ✓ Professional polish (animations, formatting, layout)
