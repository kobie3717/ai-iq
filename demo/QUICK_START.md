# Quick Start: Recording the Demo

## Prerequisites

```bash
# Install asciinema (if not already installed)
apt-get install asciinema

# Or via pip
pip install asciinema
```

## Record the Demo

```bash
cd /root/ai-iq/demo
./record.sh
```

This will:
1. Clean any previous demo database
2. Record the demo to `demo.cast`
3. Show instructions for deploying

## Deploy to Docs

```bash
# Copy the recording to docs
cp demo.cast ../docs/

# Commit and push
cd /root/ai-iq
git add demo/demo.cast docs/demo.cast docs/index.html docs/style.css
git commit -m "Add asciinema demo to homepage"
git push
```

## Preview Locally

```bash
# Open in browser
firefox /root/ai-iq/docs/index.html

# Or serve with Python
cd /root/ai-iq/docs
python3 -m http.server 8080
# Then open http://localhost:8080
```

## Customization Tips

### Make it Faster/Slower
Edit `docs/index.html` and change the `speed` parameter:
```javascript
speed: 1.5,  // 1.0 = normal, 2.0 = double speed
```

### Change Theme
Available themes: `asciinema`, `tango`, `solarized-dark`, `solarized-light`, `monokai`
```javascript
theme: 'monokai',
```

### Adjust Timing
Edit `demo-script.sh`:
- `sleep 0.03` in `type_cmd()` - typing speed per character
- `sleep 0.5` between commands - pause duration
- `sleep 1.5` after outputs - time to read results

### Change Terminal Size
Edit `record.sh` and `docs/index.html`:
```bash
# In record.sh
--cols 120  # Default: 100
--rows 35   # Default: 30

# In docs/index.html (must match)
cols: 120,
rows: 35,
```

## Troubleshooting

### Demo runs too fast
Increase `sleep` values in `demo-script.sh`

### Output is cut off
Increase `--rows` in both `record.sh` and the HTML embed

### Can't see the player
Check browser console for errors. Make sure `demo.cast` exists in `/root/ai-iq/docs/`

### Typing looks jerky
Decrease `sleep 0.03` to `sleep 0.02` in the `type_cmd()` function
