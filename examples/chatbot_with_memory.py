"""Simple chatbot that remembers what you tell it.

This example demonstrates how to use AI-IQ's Python API to build a chatbot
that remembers previous conversations and can recall related context.

Usage:
    python examples/chatbot_with_memory.py

The chatbot will:
- Store everything you say as memories
- Search for related memories when you speak
- Show you what it remembers that's relevant
"""

from ai_iq import Memory


def chat():
    """Run the chatbot with memory."""
    memory = Memory("chatbot_memory.db")

    print("🧠 Chatbot with memory. Type 'quit' to exit.")
    print("💡 Everything you say will be remembered!\n")

    while True:
        user_input = input("You: ").strip()
        if not user_input or user_input.lower() in ("quit", "exit"):
            print("\n👋 Goodbye! Your memories have been saved.")
            break

        # Store what the user says
        memory.add(user_input, tags=["chat"], category="learning")

        # Search for related memories
        results = memory.search(user_input)

        if len(results) > 1:  # More than just what we just added
            print("\n💭 I remember related things:")
            for r in results[:3]:
                if r["content"] != user_input:
                    print(f"  - {r['content']}")
            print()
        else:
            print("\n🆕 That's new! I'll remember it.\n")

    # Show statistics
    stats = memory.stats()
    print(f"\n📊 Session stats:")
    print(f"   Total memories: {stats['active']}")
    print(f"   Categories: {', '.join(stats['categories'].keys())}")


if __name__ == "__main__":
    chat()
