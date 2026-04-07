"""Complete API demonstration for AI-IQ.

Shows all major API operations with practical examples.
"""

from ai_iq import Memory


def main():
    print("=" * 70)
    print("AI-IQ Python API Demo")
    print("=" * 70)

    # 1. Initialize with custom database
    print("\n1. Creating memory instance with custom database...")
    memory = Memory("demo.db")
    print("   ✓ Memory('demo.db') created")

    # 2. Add memories (various forms)
    print("\n2. Adding memories...")

    # Simple add
    id1 = memory.add("Docker containers need network_mode: host for Redis access")
    print(f"   ✓ Added memory #{id1}")

    # Add with full options
    id2 = memory.add(
        content="Always use environment variables for secrets, never hardcode",
        category="decision",
        tags=["security", "best-practice"],  # Can use list
        project="General",
        priority=9
    )
    print(f"   ✓ Added memory #{id2} with category, tags, project, priority")

    # Add with string tags
    id3 = memory.add(
        "Redis session timeout fixed by increasing maxmemory-policy",
        category="learning",
        tags="redis,sessions,debugging",  # Can use comma-separated string
        project="MyApp"
    )
    print(f"   ✓ Added memory #{id3} with string tags")

    # 3. Search
    print("\n3. Searching for 'redis'...")
    results = memory.search("redis")
    print(f"   ✓ Found {len(results)} results")
    for r in results[:2]:
        print(f"     - #{r['id']}: {r['content'][:60]}...")

    # 4. Get specific memory
    print("\n4. Getting memory details...")
    mem = memory.get(id1)
    if mem:
        print(f"   ✓ Memory #{mem['id']}")
        print(f"     Content: {mem['content']}")
        print(f"     Category: {mem['category']}")
        print(f"     Tags: {mem['tags']}")
        print(f"     Created: {mem['created_at']}")

    # 5. Update
    print("\n5. Updating memory...")
    memory.update(id1, "Docker containers ALWAYS need network_mode: host for Redis")
    updated = memory.get(id1)
    print(f"   ✓ Updated: {updated['content']}")

    # 6. List with filters
    print("\n6. Listing memories by project...")
    project_mems = memory.list(project="MyApp")
    print(f"   ✓ Found {len(project_mems)} memories in MyApp")

    print("\n7. Listing by category...")
    decisions = memory.list(category="decision")
    print(f"   ✓ Found {len(decisions)} decision memories")

    # 8. Statistics
    print("\n8. Getting statistics...")
    stats = memory.stats()
    print(f"   ✓ Total memories: {stats['total']}")
    print(f"   ✓ Active memories: {stats['active']}")
    print(f"   ✓ Categories: {list(stats['categories'].keys())}")
    print(f"   ✓ Vector embeddings: {stats['vectors']}")

    # 9. Delete
    print("\n9. Deleting a memory...")
    memory.delete(id3)
    deleted = memory.get(id3)
    if deleted and deleted['active'] == 0:
        print(f"   ✓ Memory #{id3} soft-deleted (active=0)")

    print("\n" + "=" * 70)
    print("Demo complete! Database saved to demo.db")
    print("=" * 70)


if __name__ == "__main__":
    main()
