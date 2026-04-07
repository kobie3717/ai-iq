# START HERE: AI-IQ Demo Recording Guide

This directory contains everything you need to create and deploy a professional asciinema demo for the AI-IQ docs site.

## Quick Start (3 Commands)

```bash
cd /root/ai-iq/demo
./record.sh                    # Record the demo (~45 seconds)
cp demo.cast ../docs/          # Deploy to docs site
```

That's it! The demo is now embedded in `docs/index.html`.

## What You Get

A punchy 30-second demo (45s at 1.5x speed) showing:
1. Add memories with tags and categories
2. Hybrid search finding related memories
3. Knowledge graph with entities and relationships
4. Beliefs with confidence tracking
5. Full system stats

## File Guide

| File | Purpose | Read When |
|------|---------|-----------|
| **START_HERE.md** | This file - quick overview | First time |
| **QUICK_START.md** | Detailed step-by-step guide | Before recording |
| **RECORDING_CHECKLIST.md** | Pre-flight checklist | During recording |
| **DEMO_STORYBOARD.md** | Visual frame-by-frame guide | Planning changes |
| **IMPLEMENTATION_SUMMARY.md** | Technical details | Understanding code |
| **README.md** | Directory overview | General reference |
| **demo-script.sh** | The actual demo script | Editing/customizing |
| **record.sh** | Recording wrapper | Troubleshooting |

## Prerequisites

1. **asciinema installed**:
   ```bash
   apt-get install asciinema
   # OR
   pip install asciinema
   ```

2. **ai-iq installed**:
   ```bash
   pip install ai-iq
   which memory-tool  # Should print path
   ```

## Recording Process

### Step 1: Test the Script
```bash
cd /root/ai-iq/demo
bash demo-script.sh
```

Watch it run. Should complete in ~45 seconds with no errors.

### Step 2: Record
```bash
./record.sh
```

The script will:
- Clean the temp database
- Record to `demo.cast`
- Show next steps

### Step 3: Review
```bash
asciinema play demo.cast
```

Check:
- [ ] No errors visible
- [ ] Timing feels good (40-50 seconds)
- [ ] All text is readable
- [ ] Emojis display correctly

### Step 4: Deploy
```bash
cp demo.cast ../docs/
```

### Step 5: Test Locally
```bash
cd ../docs
python3 -m http.server 8080
# Open http://localhost:8080 in browser
```

Scroll to "See it in action" section. Demo should auto-play.

### Step 6: Commit & Push
```bash
cd /root/ai-iq
git add demo/ docs/demo.cast docs/index.html docs/style.css
git commit -m "Add asciinema demo to homepage"
git push origin main
```

## Customization

### Change Timing
Edit `demo-script.sh`:
- `sleep 0.03` in `type_cmd()` - typing speed
- `sleep 0.5` between commands - pause duration
- `sleep 1.5` after output - reading time

### Change Playback Speed
Edit `docs/index.html`:
```javascript
speed: 1.0,  // Normal speed
speed: 1.5,  // Current (punchy)
speed: 2.0,  // Double speed
```

### Change Terminal Size
Edit both `record.sh` AND `docs/index.html`:
```bash
# record.sh
--cols 120 --rows 35

# index.html
cols: 120,
rows: 35,
```

### Change Commands
Edit `demo-script.sh` and modify the `type_cmd` calls.

## Troubleshooting

### "command not found: memory-tool"
```bash
pip install ai-iq
# OR if installed but not in PATH
export PATH=$PATH:~/.local/bin
```

### Recording feels too fast/slow
After recording, adjust playback speed in `docs/index.html` (no need to re-record).

### Text is cut off
Increase `--rows` in `record.sh`, then re-record.

### Demo won't play on website
1. Check `demo.cast` exists in `docs/` directory
2. Check browser console for errors
3. Verify asciinema.js loaded from CDN

## Demo Features

This demo shows AI-IQ's key differentiators:

| Feature | Why It Matters | Shown At |
|---------|----------------|----------|
| **Categorized memories** | Better organization than flat text | 3-12s |
| **Hybrid search** | Finds connections across memories | 12-18s |
| **Knowledge graph** | Structured relationships | 18-28s |
| **Beliefs tracking** | Uncertainty/confidence handling | 28-33s |
| **Lightweight** | 24KB database, not gigabytes | 33-42s |

## Success Metrics

A good demo:
- ✓ Runs in 40-50 seconds (30-35s at 1.5x)
- ✓ Shows working CLI (not mocked)
- ✓ Demonstrates all key features
- ✓ Has clear install path
- ✓ Looks professional

## Getting Help

1. **Read QUICK_START.md** - Detailed instructions
2. **Read RECORDING_CHECKLIST.md** - Common issues
3. **Check demo-script.sh** - See what's running
4. **Test manually** - Run commands one by one

## What's Already Done

✓ Demo script created (`demo-script.sh`)
✓ Recording wrapper created (`record.sh`)
✓ HTML embed added to `docs/index.html`
✓ CSS styles added to `docs/style.css`
✓ Asciinema player configured (auto-play, 1.5x speed)

You just need to:
1. Record: `./record.sh`
2. Deploy: `cp demo.cast ../docs/`

That's it!

## Next Steps

```bash
cd /root/ai-iq/demo
./record.sh
```

Then follow the on-screen instructions.

---

**Questions?** Check the other .md files in this directory for detailed guides.
