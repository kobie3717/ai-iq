"""Most basic AI-IQ usage example.

This is the minimal example shown in the README.
"""

from ai_iq import Memory

# Initialize
memory = Memory()

# Add memories
memory.add("User prefers dark mode", tags=["preference", "ui"])
memory.add(
    "Redis session bug fixed with network_mode: host",
    category="learning",
    project="MyApp"
)

# Search (hybrid keyword + semantic)
results = memory.search("redis networking")
for r in results[:3]:
    print(f"#{r['id']}: {r['content']}")

# Update and delete
mem_id = results[0]["id"]
memory.update(mem_id, "Redis ALWAYS needs network_mode: host in Docker")
print(f"\n✓ Updated memory #{mem_id}")

# Get statistics
stats = memory.stats()
print(f"\n📊 Total memories: {stats['active']}")
print(f"📁 Categories: {', '.join(stats['categories'].keys())}")
