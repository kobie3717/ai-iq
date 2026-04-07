#!/bin/bash
# AI-IQ Plugin Setup Wrapper
# Called by Claude Code plugin system via Setup hook

set -e

# Determine plugin root
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
if [ -z "$PLUGIN_ROOT" ]; then
    PLUGIN_ROOT="$HOME/.claude/plugins/marketplaces/kobie3717/ai-iq"
fi

echo "=== AI-IQ Plugin Setup ==="
echo "Plugin root: $PLUGIN_ROOT"
echo ""

# Step 1: Check if ai-iq is installed
if command -v memory-tool &> /dev/null; then
    echo "✓ memory-tool is already installed"
else
    echo "Installing ai-iq via pip..."
    if pip install ai-iq; then
        echo "✓ ai-iq installed successfully"
    else
        echo "WARNING: Could not install ai-iq. Please run: pip install ai-iq"
        exit 0  # Don't fail setup
    fi
fi

# Step 2: Initialize memory database if needed
if [ ! -f "$HOME/.ai-iq/memories.db" ]; then
    echo "Initializing AI-IQ memory database..."
    mkdir -p "$HOME/.ai-iq"
    memory-tool stats > /dev/null 2>&1 || true  # Initialize DB
    echo "✓ Memory database initialized at $HOME/.ai-iq/memories.db"
else
    echo "✓ Memory database already exists"
fi

echo ""
echo "=== AI-IQ Plugin Ready ==="
echo ""
echo "Quick start:"
echo "  memory-tool add learning \"Your first memory\" --project MyProject"
echo "  memory-tool search \"memory\""
echo "  memory-tool next  # Smart suggestions"
echo ""
echo "See /skills/memory for full documentation"
echo ""

exit 0
