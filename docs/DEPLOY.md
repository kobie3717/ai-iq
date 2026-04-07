# GitHub Pages Deployment Guide

This documentation site is designed for GitHub Pages hosting at `kobie3717.github.io/ai-iq`.

## Setup GitHub Pages

1. Go to your GitHub repository: https://github.com/kobie3717/ai-iq
2. Navigate to **Settings** > **Pages**
3. Under **Source**, select:
   - Branch: `main`
   - Folder: `/docs`
4. Click **Save**

GitHub Pages will automatically deploy from the `/docs` folder.

## Custom Domain (Optional)

To use a custom domain:

1. Edit `docs/CNAME` and add your domain (e.g., `ai-iq.dev`)
2. Configure DNS:
   - Add CNAME record pointing to `kobie3717.github.io`
   - Or A records to GitHub Pages IPs (185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153)
3. Commit and push changes

## Local Testing

To preview locally:

```bash
cd /root/ai-iq/docs
python3 -m http.server 8000
```

Visit http://localhost:8000

## Files

- `index.html` - Main documentation page (single-page design)
- `style.css` - Dark theme styling
- `CNAME` - Custom domain configuration (optional)

## No Build Required

This is a static site with no build step. GitHub Pages serves the files directly.
- No Jekyll
- No frameworks
- No dependencies
- Pure HTML/CSS/JS

## CDN Resources

The site uses these CDN resources:
- Prism.js (syntax highlighting)
- Badges from shields.io

All CDN resources have fallbacks and won't break the site if unavailable.

## Updates

To update the docs:

1. Edit `docs/index.html` or `docs/style.css`
2. Commit and push to `main` branch
3. GitHub Pages will automatically redeploy (usually takes 1-2 minutes)

## Monitoring

Check deployment status:
- GitHub Actions: https://github.com/kobie3717/ai-iq/actions
- Pages: https://github.com/kobie3717/ai-iq/deployments

Live site will be available at: https://kobie3717.github.io/ai-iq
