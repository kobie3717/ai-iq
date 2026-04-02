# Recording & Deployment Checklist

Use this checklist when recording and deploying the AI-IQ demo.

## Pre-Recording Checklist

- [ ] **Install asciinema**: `apt-get install asciinema` or `pip install asciinema`
- [ ] **Verify ai-iq installed**: `which memory-tool`
- [ ] **Clean previous demo DB**: `rm -f /tmp/ai-iq-demo.db`
- [ ] **Test demo script**: `bash /root/ai-iq/demo/demo-script.sh` (watch for errors)
- [ ] **Set terminal size**: Resize terminal to ~100 cols x 30 rows for consistency
- [ ] **Clear terminal**: `clear` before starting

## Recording

- [ ] **Navigate to demo directory**: `cd /root/ai-iq/demo`
- [ ] **Run record script**: `./record.sh`
- [ ] **Wait for completion**: Script will run ~45 seconds
- [ ] **Verify recording created**: `ls -lh demo.cast`

## Post-Recording Review

- [ ] **Play back recording**: `asciinema play demo.cast`
- [ ] **Check timing**: Total should be 40-50 seconds
- [ ] **Verify all commands worked**: No error messages visible
- [ ] **Check readability**: Text is clear and not cut off
- [ ] **Verify emojis display**: Section headers show correctly

### If Issues Found:
- Timing too fast/slow? → Edit sleep values in `demo-script.sh`
- Commands failed? → Check ai-iq installation
- Text cut off? → Increase `--rows` in `record.sh`
- Re-record: `./record.sh` (auto-overwrites)

## Deployment

- [ ] **Copy to docs**: `cp demo.cast ../docs/`
- [ ] **Verify file exists**: `ls -lh ../docs/demo.cast`
- [ ] **Test HTML embed**: Open `docs/index.html` in browser
- [ ] **Check autoplay**: Demo starts automatically when scrolling to it
- [ ] **Verify 1.5x speed**: Demo feels punchy, not sluggish
- [ ] **Test on mobile**: Responsive layout works on narrow screens

## Git Commit

- [ ] **Stage all files**:
  ```bash
  cd /root/ai-iq
  git add demo/ docs/demo.cast docs/index.html docs/style.css
  ```

- [ ] **Review changes**: `git diff --staged`

- [ ] **Commit with message**:
  ```bash
  git commit -m "Add asciinema demo to homepage

  - Created demo script with typing animation
  - Shows 5 key features in <45s: memories, search, graph, beliefs, stats
  - Embedded with asciinema player in docs/index.html
  - Auto-plays at 1.5x speed for punchy feel
  - Dark theme (monokai) matches site aesthetic"
  ```

- [ ] **Push to GitHub**: `git push origin main`

## Post-Deployment Verification

- [ ] **Check GitHub Pages**: Visit deployed site (if using GH Pages)
- [ ] **Verify player loads**: asciinema.js loaded from CDN
- [ ] **Check across browsers**: Chrome, Firefox, Safari
- [ ] **Mobile responsive**: Test on phone/tablet
- [ ] **Page load speed**: Demo doesn't slow down initial load
- [ ] **Analytics**: Track engagement if available

## Optional: Social Media Sharing

- [ ] **Upload to asciinema.org**: `asciinema upload demo.cast`
- [ ] **Get shareable link**: Copy URL from asciinema.org
- [ ] **Share on Twitter/X**: "Check out AI-IQ demo" + link
- [ ] **Post on Reddit**: r/Python, r/opensource, r/programming
- [ ] **LinkedIn**: Share with #AI #opensource #Python tags
- [ ] **Hacker News**: Submit with demo link

## Maintenance Schedule

- [ ] **Re-record quarterly**: Keep demo fresh with latest features
- [ ] **Update timing**: Adjust speed based on user feedback
- [ ] **A/B test variants**: Try different speeds/themes
- [ ] **Monitor drop-off**: Where do users stop watching?

## Quick Fixes

### Demo won't record
```bash
# Check asciinema version
asciinema --version

# Reinstall if needed
pip install --upgrade asciinema
```

### Player doesn't load on site
```bash
# Check demo.cast exists
ls /root/ai-iq/docs/demo.cast

# Verify file is valid JSON
head /root/ai-iq/docs/demo.cast
```

### Timing feels off
Edit `docs/index.html`:
```javascript
speed: 1.2,  // Slower
speed: 2.0,  // Faster
```

---

**Notes:**
- Always test locally before pushing
- Keep demo.cast under 1MB for fast loading
- Monitor user feedback for timing adjustments
- Consider creating alternate demos for different audiences
