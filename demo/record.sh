#!/bin/bash
# Record AI-IQ demo with asciinema

# Clean any previous demo
export AI_IQ_DB=/tmp/ai-iq-demo.db
rm -f /tmp/ai-iq-demo.db

# Record with tight settings for web embed
asciinema rec /root/ai-iq/demo/demo.cast \
  --title "AI-IQ: SQLite for AI memory" \
  --cols 100 \
  --rows 30 \
  --overwrite \
  --command "bash /root/ai-iq/demo/demo-script.sh"

echo ""
echo "✅ Demo recorded to /root/ai-iq/demo/demo.cast"
echo "📋 Copy to docs: cp /root/ai-iq/demo/demo.cast /root/ai-iq/docs/"
echo "🌐 Embed in docs/index.html (asciinema player already added)"
