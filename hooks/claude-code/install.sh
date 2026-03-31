#!/bin/bash
# AI-IQ Claude Code Plugin Installer
# Installs memory-tool and configures Claude Code hooks

set -e

echo "=== AI-IQ Claude Code Plugin Installer ==="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Determine Claude Code settings location
if [[ "$OSTYPE" == "darwin"* ]]; then
    CLAUDE_DIR="$HOME/.claude"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    CLAUDE_DIR="$HOME/.claude"
else
    echo -e "${RED}ERROR: Unsupported OS${NC}"
    exit 1
fi

SETTINGS_FILE="$CLAUDE_DIR/settings.json"
SETTINGS_LOCAL_FILE="$CLAUDE_DIR/settings.local.json"

# Step 1: Check if memory-tool is installed
echo "Step 1: Checking for memory-tool..."
if command -v memory-tool &> /dev/null; then
    echo -e "${GREEN}✓ memory-tool is already installed${NC}"
    memory-tool --version 2>/dev/null || echo "(version unknown)"
else
    echo -e "${YELLOW}Installing memory-tool via pip...${NC}"
    pip install ai-iq

    if command -v memory-tool &> /dev/null; then
        echo -e "${GREEN}✓ memory-tool installed successfully${NC}"
    else
        echo -e "${RED}ERROR: memory-tool installation failed${NC}"
        echo "Try: pip install --user ai-iq"
        echo "Then ensure ~/.local/bin is in your PATH"
        exit 1
    fi
fi

echo ""

# Step 2: Create Claude Code directory if it doesn't exist
echo "Step 2: Setting up Claude Code directories..."
mkdir -p "$CLAUDE_DIR/hooks"
echo -e "${GREEN}✓ Created $CLAUDE_DIR/hooks${NC}"
echo ""

# Step 3: Copy hook scripts
echo "Step 3: Installing hook scripts..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp "$SCRIPT_DIR/error-hook.sh" "$CLAUDE_DIR/hooks/ai-iq-error-hook.sh"
chmod +x "$CLAUDE_DIR/hooks/ai-iq-error-hook.sh"
echo -e "${GREEN}✓ Installed error-hook.sh${NC}"

cp "$SCRIPT_DIR/session-hook.sh" "$CLAUDE_DIR/hooks/ai-iq-session-hook.sh"
chmod +x "$CLAUDE_DIR/hooks/ai-iq-session-hook.sh"
echo -e "${GREEN}✓ Installed session-hook.sh${NC}"

cp "$SCRIPT_DIR/session-start-hook.sh" "$CLAUDE_DIR/hooks/ai-iq-session-start-hook.sh"
chmod +x "$CLAUDE_DIR/hooks/ai-iq-session-start-hook.sh"
echo -e "${GREEN}✓ Installed session-start-hook.sh${NC}"

echo ""

# Step 4: Configure hooks in settings.json
echo "Step 4: Configuring Claude Code hooks..."

# Check if settings.json exists
if [ ! -f "$SETTINGS_FILE" ]; then
    echo -e "${YELLOW}Creating new settings.json...${NC}"
    cat > "$SETTINGS_FILE" << 'EOF'
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/ai-iq-session-hook.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/ai-iq-error-hook.sh"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/ai-iq-session-start-hook.sh"
          }
        ]
      }
    ]
  }
}
EOF
    echo -e "${GREEN}✓ Created settings.json with AI-IQ hooks${NC}"
else
    echo -e "${YELLOW}Existing settings.json found${NC}"
    echo "You'll need to manually add the hooks to your settings.json"
    echo ""
    echo "Add these hook configurations to your ~/.claude/settings.json:"
    echo ""
    cat << 'EOF'
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/ai-iq-session-hook.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/ai-iq-error-hook.sh"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/ai-iq-session-start-hook.sh"
          }
        ]
      }
    ]
  }
}
EOF
    echo ""
    echo "Note: If you already have hooks, add these to the existing arrays."
fi

echo ""

# Step 5: Install daily maintenance cron (optional)
echo "Step 5: Daily maintenance cron (optional)..."
echo "Would you like to install a daily maintenance cron job? (y/N)"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    # Check if cron job already exists
    if crontab -l 2>/dev/null | grep -q "ai-iq-daily-maintenance.sh"; then
        echo -e "${YELLOW}Cron job already exists, skipping${NC}"
    else
        cp "$SCRIPT_DIR/daily-maintenance.sh" "$CLAUDE_DIR/hooks/ai-iq-daily-maintenance.sh"
        chmod +x "$CLAUDE_DIR/hooks/ai-iq-daily-maintenance.sh"

        # Add cron job
        (crontab -l 2>/dev/null; echo "17 3 * * * bash $CLAUDE_DIR/hooks/ai-iq-daily-maintenance.sh") | crontab -
        echo -e "${GREEN}✓ Daily maintenance cron job installed (runs at 3:17 AM)${NC}"
    fi
else
    echo "Skipped cron installation (you can run maintenance manually with: memory-tool decay && memory-tool gc && memory-tool backup)"
fi

echo ""

# Step 6: Show CLAUDE.md instructions
echo "=== Installation Complete! ==="
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo ""
echo "1. Add the AI-IQ memory system to your project's CLAUDE.md file:"
echo ""
echo "   cat $SCRIPT_DIR/CLAUDE.md.example >> /your/project/CLAUDE.md"
echo ""
echo "2. Initialize memory for your project:"
echo ""
echo "   cd /your/project"
echo "   memory-tool add project \"Brief description of your project\" --project MyProject"
echo ""
echo "3. Start using Claude Code - memories will be auto-captured!"
echo ""
echo "4. View your memory stats:"
echo ""
echo "   memory-tool stats"
echo ""
echo -e "${YELLOW}Installed hooks:${NC}"
echo "  - PostToolUse (Bash): Auto-captures failed commands"
echo "  - Stop: Auto-snapshots session + decay + export + backup"
echo "  - SessionStart: Logs session start for timeline"
echo ""
echo "Run 'memory-tool --help' for all available commands."
echo ""
