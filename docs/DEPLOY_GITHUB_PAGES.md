# GitHub Pages Deployment Guide

This directory contains the static site for AI-IQ documentation, designed to be served via GitHub Pages.

## Site Structure

```
docs/
├── .nojekyll          # Tells GitHub Pages to skip Jekyll processing
├── index.html         # Landing page with hero, features, comparison table
├── quickstart.html    # Getting started guide
├── api.html           # Python API reference
├── cli.html           # CLI command reference
├── plugins.html       # Claude Code plugin docs (existing)
├── reference.html     # Full reference (existing)
├── style.css          # Shared stylesheet (dark theme, rust orange accent)
└── DEPLOY_GITHUB_PAGES.md  # This file
```

## Deployment Steps

### 1. Enable GitHub Pages

1. Go to repository settings: https://github.com/kobie3717/ai-iq/settings/pages
2. Under "Source", select:
   - Branch: `main`
   - Folder: `/docs`
3. Click "Save"

### 2. Wait for Deployment

GitHub Pages will automatically deploy within 1-2 minutes. Check the deployment status:
- Visit: https://github.com/kobie3717/ai-iq/deployments

### 3. Access the Site

Once deployed, the site will be available at:
- **Production URL**: https://kobie3717.github.io/ai-iq/

## Design Features

- **Dark theme**: Navy/charcoal background with light text
- **Accent color**: #FF6B35 (rust/crab orange) matching the 🦀 brand
- **Responsive**: Mobile-friendly design
- **Zero build tools**: Pure HTML/CSS/JS, no bundlers needed
- **Syntax highlighting**: Prism.js from CDN for code blocks
- **Professional**: Clean, modern design inspired by Stripe/Tailwind docs

## Navigation Structure

- **Home** (index.html) — Landing page with features and comparison
- **Quick Start** (quickstart.html) — Installation and basic usage
- **API** (api.html) — Complete Python API reference
- **CLI** (cli.html) — Complete CLI command reference
- **GitHub** — Link to repository

## Testing Locally

To test the site locally before pushing:

```bash
# Option 1: Python simple HTTP server
cd /root/ai-iq/docs
python3 -m http.server 8000
# Visit: http://localhost:8000

# Option 2: Node.js http-server
npm install -g http-server
cd /root/ai-iq/docs
http-server -p 8000
# Visit: http://localhost:8000
```

## Content Updates

### To update content:

1. **Edit HTML files directly** — No build process needed
2. **Update style.css** for styling changes
3. **Commit and push** — GitHub Pages auto-deploys from `/docs`

### To add a new page:

1. Create `newpage.html` in `/docs`
2. Copy navigation structure from existing pages
3. Update nav links in all pages to include the new page
4. Commit and push

## Troubleshooting

### Site not updating?

- Check GitHub Actions status: https://github.com/kobie3717/ai-iq/actions
- Clear browser cache (Cmd+Shift+R or Ctrl+Shift+R)
- Verify `/docs` is selected as source in settings

### Styles not loading?

- Ensure `.nojekyll` file exists (prevents Jekyll from ignoring CSS)
- Check browser console for 404 errors
- Verify all paths are relative (no leading `/`)

## Performance

- All assets load from CDN (Prism.js for syntax highlighting)
- No JavaScript frameworks (vanilla JS only)
- Minimal CSS (single ~12KB file)
- Fast page loads (<500ms typical)

## SEO

Each page includes:
- Proper `<title>` tags
- Meta descriptions for search engines
- Semantic HTML structure
- Favicon (crab emoji)

## Maintenance

- **No dependencies** to update (static HTML/CSS/JS)
- **No build process** to maintain
- **No CI/CD** required (GitHub Pages handles it)
- Just edit, commit, push — site updates automatically

---

Built with plain HTML, CSS, and JavaScript. No frameworks. No build tools. Just works.
