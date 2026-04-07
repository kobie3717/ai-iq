# AI-IQ Docs Site Deployment Guide

## Overview

The AI-IQ documentation site is built with plain HTML/CSS/JS (no build tools) and designed to be hosted on GitHub Pages at `kobie3717.github.io/ai-iq/`.

## File Structure

```
/root/ai-iq/docs/
├── _config.yml           # GitHub Pages config (theme: null for custom HTML)
├── index.html            # Homepage (landing page)
├── quickstart.html       # Getting started guide
├── reference.html        # Complete CLI and Python API reference
├── plugins.html          # Claude Code plugin setup
├── style.css             # Shared styles (dark theme)
└── REFERENCE.md          # Source markdown for reference content
```

## Deployment Steps

### 1. Commit and Push

```bash
cd /root/ai-iq
git add docs/
git commit -m "docs: add GitHub Pages site with quickstart, reference, and plugins pages"
git push origin main
```

### 2. Enable GitHub Pages

1. Go to https://github.com/kobie3717/ai-iq/settings/pages
2. Under "Source", select:
   - Branch: `main`
   - Folder: `/docs`
3. Click "Save"
4. GitHub will build and deploy the site

### 3. Verify Deployment

Site will be available at: https://kobie3717.github.io/ai-iq/

Pages:
- https://kobie3717.github.io/ai-iq/ (homepage)
- https://kobie3717.github.io/ai-iq/quickstart.html
- https://kobie3717.github.io/ai-iq/reference.html
- https://kobie3717.github.io/ai-iq/plugins.html

## Custom Domain (Optional)

To use a custom domain like `ai-iq.dev`:

1. Create `/root/ai-iq/docs/CNAME` with content:
   ```
   ai-iq.dev
   ```

2. Add DNS records at your domain registrar:
   ```
   A    @    185.199.108.153
   A    @    185.199.109.153
   A    @    185.199.110.153
   A    @    185.199.111.153
   CNAME www  kobie3717.github.io
   ```

3. Enable HTTPS in GitHub Pages settings

## Features

### Design
- **Dark theme** — Developer-friendly dark background with teal accent (#00D9C0)
- **Responsive** — Mobile-friendly layout
- **Syntax highlighting** — Prism.js for Python and Bash code blocks
- **Copy buttons** — One-click code copying
- **Smooth navigation** — Sticky header, smooth scrolling

### Pages

#### index.html (Homepage)
- Hero section with pip install
- Why AI-IQ? feature cards
- Quick start examples (Python, CLI, Plugin)
- Python API reference
- CLI reference tables
- Advanced features showcase
- Comparison table (AI-IQ vs Mem0/Zep/Letta)
- Production stats
- CTA section

#### quickstart.html
- Installation instructions
- Python API basics (5 lines to first memory)
- CLI usage basics
- Memory categories explanation
- First 5 minutes tutorial
- Python integration example
- Search modes explanation

#### reference.html
- Sidebar navigation with active link tracking
- Complete CLI command reference organized by category:
  - Core Operations
  - Search & Discovery
  - Beliefs & Predictions
  - Knowledge Graph
  - Identity & Narrative
  - Meta-Learning
  - Session Management
  - Maintenance
  - Cross-Tool Sync
- Complete Python API reference
- Code examples for every command

#### plugins.html
- What the plugin does
- Quick install instructions
- Hook details (PostToolUse, Stop, SessionStart)
- Manual installation steps
- Daily maintenance cron setup
- Usage examples
- Configuration options
- Troubleshooting guide

### Technical Details
- **No build tools** — Pure HTML/CSS/JS
- **CDN dependencies** — Prism.js for syntax highlighting
- **Relative links** — All navigation uses relative paths
- **GitHub Pages ready** — `_config.yml` with `theme: null`

## Maintenance

### Updating Content

1. **Edit HTML files directly** for content changes
2. **Edit style.css** for design changes
3. **Keep REFERENCE.md in sync** with reference.html

### Adding New Pages

1. Create new `.html` file in `/root/ai-iq/docs/`
2. Use existing pages as templates
3. Add navigation link to all pages
4. Commit and push

### Testing Locally

Since it's static HTML, just open files in a browser:

```bash
# Start a simple HTTP server
cd /root/ai-iq/docs
python3 -m http.server 8000

# Visit http://localhost:8000/
```

## Performance

- **Lightweight** — No JavaScript frameworks
- **Fast loading** — Minimal CSS, CDN-hosted Prism.js
- **SEO-friendly** — Semantic HTML, meta tags

## Analytics (Optional)

To add Google Analytics:

1. Get tracking ID from https://analytics.google.com
2. Add before `</head>` in all HTML files:

```html
<!-- Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

## Troubleshooting

### Site not updating
- Check GitHub Actions tab for build status
- Clear browser cache
- Wait 5-10 minutes for CDN propagation

### Broken links
- All links use relative paths (e.g., `quickstart.html` not `/quickstart.html`)
- This ensures they work both locally and on GitHub Pages

### Styling issues
- Check browser console for CSS load errors
- Verify Prism.js CDN is accessible
- Test in different browsers

## Future Improvements

- [ ] Search functionality (Algolia/Fuse.js)
- [ ] Dark/light theme toggle
- [ ] Interactive examples (CodePen embeds)
- [ ] Video tutorials
- [ ] API playground
- [ ] Change log page
- [ ] Blog section

## Questions?

Open an issue at: https://github.com/kobie3717/ai-iq/issues
