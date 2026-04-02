# AI-IQ Documentation Site

This directory contains the GitHub Pages documentation site for AI-IQ.

## Deployment

The site is hosted at: **https://kobie3717.github.io/ai-iq/**

### GitHub Pages Setup

1. Push the `docs/` folder to the `main` branch
2. Go to your GitHub repository settings
3. Navigate to **Settings** → **Pages**
4. Under "Source", select:
   - Branch: `main`
   - Folder: `/docs`
5. Click "Save"
6. GitHub will build and deploy the site automatically (takes 1-2 minutes)

### Local Development

To preview the site locally:

```bash
# Simple HTTP server (Python)
cd /root/ai-iq/docs
python3 -m http.server 8000

# Or use Node.js http-server
npx http-server .

# Visit http://localhost:8000 in your browser
```

## Files

- **index.html** - Main docs site (single-file, self-contained)
- **REFERENCE.md** - Complete CLI/API reference (linked from index.html)
- **FEEDBACK_SYSTEM.md** - Meta-learning feedback system docs
- **FEEDBACK_QUICKSTART.md** - Quick start guide for feedback features

## Updating the Site

Simply edit `index.html` and push to GitHub. Changes will be live within 1-2 minutes.

The site is built with:
- Zero build tools (pure HTML/CSS/JS)
- Dark theme optimized for developers
- Responsive design (mobile-friendly)
- Smooth scroll navigation
- Syntax-highlighted code examples
- Google Fonts (Inter + JetBrains Mono)

## Design Principles

- **Single file** - No build process, easy to maintain
- **Fast** - Minimal dependencies, loads instantly
- **Accessible** - Semantic HTML, keyboard navigation
- **Professional** - Clean design inspired by Stripe/Tailwind docs
