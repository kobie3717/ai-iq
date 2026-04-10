#!/usr/bin/env python3
"""Migrate existing memories to appropriate tiers."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from memory_tool.database import get_db
from memory_tool.tiers import classify_tier
from datetime import datetime

def migrate_existing_tiers():
    """Classify all existing memories into tiers."""
    conn = get_db()
    
    # Get all active memories
    memories = conn.execute("""
        SELECT id, category, priority, tags, proof_count, expires_at, access_count, tier, created_at
        FROM memories
        WHERE active = 1
    """).fetchall()
    
    updated = {'semantic': 0, 'episodic': 0, 'working': 0, 'no_change': 0}
    
    for mem in memories:
        # Build memory row dict for classification
        memory_row = {
            'category': mem['category'],
            'priority': mem['priority'] or 0,
            'tags': mem['tags'] or '',
            'proof_count': mem['proof_count'] or 1,
            'expires_at': mem['expires_at'],
            'access_count': mem['access_count'] or 0,
        }
        
        # Get recommended tier
        recommended_tier = classify_tier(memory_row)
        current_tier = mem['tier'] or 'episodic'
        
        # Update if different
        if recommended_tier != current_tier:
            conn.execute("UPDATE memories SET tier = ? WHERE id = ?", (recommended_tier, mem['id']))
            updated[recommended_tier] += 1
        else:
            updated['no_change'] += 1
    
    conn.commit()
    
    # Show final distribution
    final_stats = conn.execute("""
        SELECT tier, COUNT(*) as count
        FROM memories
        WHERE active = 1
        GROUP BY tier
    """).fetchall()
    
    print("Migration Complete!")
    print(f"\nUpdated:")
    print(f"  → semantic: {updated['semantic']}")
    print(f"  → episodic: {updated['episodic']}")
    print(f"  → working: {updated['working']}")
    print(f"  No change: {updated['no_change']}")
    
    print("\nFinal distribution:")
    for row in final_stats:
        tier = row['tier'] or 'NULL'
        print(f"  {tier}: {row['count']}")
    
    conn.close()

if __name__ == '__main__':
    migrate_existing_tiers()
