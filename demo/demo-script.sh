#!/bin/bash
# AI-IQ Demo Script - Fast-paced showcase in under 45 seconds

# Use temp database for clean demo
export AI_IQ_DB=/tmp/ai-iq-demo.db

# Type command with realistic timing
type_cmd() {
    local cmd="$1"
    echo -n "$ "
    for ((i=0; i<${#cmd}; i++)); do
        printf '%s' "${cmd:$i:1}"
        sleep 0.03
    done
    echo ""
    eval "$cmd"
}

# Clear
clear

# Intro
echo ""
echo "# 🦀 AI-IQ: SQLite for AI memory"
echo "# pip install ai-iq"
echo ""
sleep 1

# 1. Add memories
echo "# 💾 Store memories with context"
sleep 0.5
type_cmd 'memory-tool add project "WhatsApp auction platform launched - 50 users in first week" --tags launch,growth'
sleep 0.5
type_cmd 'memory-tool add decision "Switched from REST to WebSocket for real-time bidding - 3x faster" --tags architecture'
sleep 0.5
type_cmd 'memory-tool add learning "PostgreSQL NOTIFY/LISTEN better than polling for auction events" --tags database,performance'
sleep 0.5
type_cmd 'memory-tool add error "Memory leak in WebSocket handler - connections not cleaned up on disconnect" --tags bug,websocket'
sleep 0.5

echo ""
echo "# 🔍 Hybrid search finds connections across memories"
sleep 0.5
type_cmd 'memory-tool search "real-time performance"'
sleep 1.5

echo ""
echo "# 🕸️  Build knowledge graphs"
sleep 0.5
type_cmd 'memory-tool graph add project AuctionApp'
sleep 0.3
type_cmd 'memory-tool graph add tool WebSocket'
sleep 0.3
type_cmd 'memory-tool graph rel AuctionApp uses WebSocket'
sleep 0.5
type_cmd 'memory-tool graph get AuctionApp'
sleep 1.5

echo ""
echo "# 🎯 Track beliefs with confidence"
sleep 0.5
type_cmd 'memory-tool believe "WebSocket scales to 10k concurrent users" --confidence 0.7'
sleep 0.5
type_cmd 'memory-tool beliefs'
sleep 1.5

echo ""
echo "# 📊 Full system stats"
sleep 0.5
type_cmd 'memory-tool stats'
sleep 2

echo ""
echo "# ✨ Install: pip install ai-iq"
echo "# 📚 Docs: https://github.com/kobie3717/ai-iq"
echo ""
