# AI-IQ Demo Recording

This directory contains the asciinema demo for the AI-IQ docs homepage.

## Files

- **demo-script.sh** - The demo script with typing animation
- **record.sh** - Records the demo to demo.cast
- **demo.cast** - The recorded asciinema file (copy to docs/)

## Recording the Demo

1. Make sure ai-iq is installed:
   ```bash
   pip install ai-iq
   ```

2. Record the demo:
   ```bash
   cd /root/ai-iq/demo
   ./record.sh
   ```

3. Copy to docs directory:
   ```bash
   cp demo.cast ../docs/
   ```

4. The demo is already embedded in `docs/index.html` using the asciinema player.

## Testing Locally

Open `docs/index.html` in a browser to see the embedded demo. Make sure `demo.cast` is in the same directory.

## Demo Flow (< 45 seconds at normal speed)

1. **Intro** - Show pip install
2. **Add memories** - 4 different memories with tags
3. **Hybrid search** - Show search finding related memories
4. **Knowledge graph** - Add entities and relationships
5. **Beliefs** - Track confidence in statements
6. **Stats** - Show full system overview

Plays at 1.5x speed on the website for a punchy feel.

## Customizing

Edit `demo-script.sh` to change:
- Commands shown
- Timing (sleep values)
- Typing speed (0.03s per char)
- Demo database path (default: /tmp/ai-iq-demo.db)
