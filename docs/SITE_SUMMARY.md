# AI-IQ Documentation Site

## Overview

Professional, dark-themed GitHub Pages documentation site for AI-IQ.

**Live URL**: https://kobie3717.github.io/ai-iq (after deployment)

## Design Principles

1. **Dark Theme** - Modern dev-tool aesthetic (Stripe/Vercel vibes)
2. **Single Page** - All content on one page with smooth scroll navigation
3. **Fast & Clean** - No build tools, no frameworks, no bloat
4. **Mobile Responsive** - Works perfectly on all screen sizes
5. **Professional** - Competes with established projects (mem0, etc.)

## Features

- **Navbar** - Sticky navigation with smooth scroll, GitHub link
- **Hero Section** - Big impact tagline, install command, badges
- **Why AI-IQ?** - 6 feature cards highlighting unique selling points
- **Quick Start** - Python API, CLI, and Claude Code plugin examples
- **Python API Reference** - Complete API documentation with examples
- **CLI Reference** - All commands organized in clean tables
- **Advanced Features** - Detailed feature explanations with code samples
- **Comparison Table** - AI-IQ vs. competitors (Mem0, Zep, Letta)
- **Production Stats** - Real-world usage statistics
- **CTA Section** - Install command, links to GitHub/PyPI/Examples
- **Copy Buttons** - One-click copy for all code blocks
- **Syntax Highlighting** - Prism.js for Python and Bash

## Technical Stack

- **HTML5** - Semantic markup
- **CSS3** - Custom properties, flexbox, grid
- **Vanilla JS** - Copy buttons, smooth scroll, navbar effects
- **Prism.js** - Syntax highlighting (from CDN)
- **Shields.io** - Badges (from CDN)

## Color Palette

- Background: #0D1117 (dark), #010409 (darker)
- Text: #E6EDF3 (primary), #8B949E (secondary)
- Accent: #00D9C0 (teal/cyan gradient)
- Borders: #30363D

## File Structure

```
docs/
├── index.html      # Main documentation page (729 lines)
├── style.css       # Styling (681 lines)
├── CNAME           # Custom domain config (empty)
├── DEPLOY.md       # Deployment instructions
└── SITE_SUMMARY.md # This file
```

## Deployment

1. Go to GitHub repo settings > Pages
2. Select source: Branch `main`, Folder `/docs`
3. Save

Site deploys automatically in ~2 minutes.

## Content Highlights

### Hero
- "SQLite for AI Memory"
- "No servers. No setup. Just memory."
- One-line install: `pip install ai-iq`

### Key Differentiators
- Single SQLite file (no servers)
- 100% local (no cloud dependencies)
- Vendor-agnostic (works with any Python agent)
- Hybrid search (keyword + semantic + graph)
- Natural decay (FSRS-6 algorithm)
- Dream mode (REM-like consolidation)

### Unique Features (vs. competitors)
- Beliefs & Predictions (Bayesian confidence tracking)
- Dream consolidation (autonomous cleanup)
- Identity layer (behavioral trait discovery)
- Narrative memory (causal chains)
- Meta-learning search (self-improving weights)

### Production Proof
- 220+ active memories
- 697 duplicates consolidated
- 32 entities in graph
- 18 beliefs tracked
- 12 predictions resolved
- 0 data loss incidents

## SEO Considerations

- Title: "AI-IQ — SQLite for AI Memory"
- Description: "Give your AI long-term memory in one command. No servers. No setup. Just memory."
- Brain emoji favicon
- Semantic HTML structure
- Fast load time (no heavy assets)

## Next Steps

1. Deploy to GitHub Pages
2. Monitor traffic/analytics
3. Add custom domain (optional)
4. Consider adding:
   - Blog section
   - Changelog page
   - Community/Discord links
   - Video demos

## Maintenance

To update:
1. Edit `docs/index.html` or `docs/style.css`
2. Commit and push to `main`
3. GitHub Pages auto-deploys

No build step required.
