# Google Search Console — indexing monitor (GeoRisk Engine)

Use this runbook after deploying marketing-site changes (especially `/contact`, `sitemap.xml`, and `robots.txt`).

## Baseline (CSV export)

| Metric | Value | Date |
|--------|-------|------|
| Indexed pages | 1 | 2026-05-22 |
| Not indexed | 3 | 2026-05-22 |
| Impressions | 3 | 2026-05-22 |

Property: `https://georiskengine.com/` (confirm exact GSC property URL — apex vs `www`).

## Pre-flight (repo)

| Check | Expected | Command / location |
|-------|----------|-------------------|
| Sitemap lists `/`, `/contact`, `/hizmetler` | 3 `<loc>` entries | `frontend/public/sitemap.xml` |
| `robots.txt` allows crawl + sitemap URL | `Allow: /` + `Sitemap:` line | `frontend/public/robots.txt` |
| Vite emits static assets | `dist/sitemap.xml`, `dist/robots.txt`, `dist/contact.html` | `npm run build --prefix frontend` |
| `/contact` rewrite | `/contact` → `contact.html` | `vercel.json` |
| `/hizmetler` rewrite | `/hizmetler` → `hizmetler.html` | `vercel.json` |

## Post-deploy HTTP checks (production)

Run after Vercel deploy from `main` (or preview URL for PR validation):

```bash
BASE="https://georiskengine.com"
for path in "/" "/contact" "/hizmetler" "/robots.txt" "/sitemap.xml"; do
  code=$(curl -sS -o /dev/null -w "%{http_code}" "${BASE}${path}")
  echo "${path} -> ${code}"
done
```

**Pass criteria:** all paths return `200`.  
**HTML pages:** response body must contain real content without executing JavaScript (view source or `curl` and grep for `<title>`).

### `/contact` without JavaScript

```bash
curl -sS "https://georiskengine.com/contact" | head -20
# Expect: <!DOCTYPE html> and <title>Contact GeoRisk Engine</title>
```

The contact page is static HTML; no client bundle is required for rendering.

## Google Search Console — manual steps

1. **Confirm property** matches the canonical host you deploy (`georiskengine.com` vs `www.georiskengine.com`). Set redirects so only one host is primary; update `sitemap.xml` `<loc>` values to match.
2. **Sitemaps** → Submit `https://georiskengine.com/sitemap.xml` (re-submit after each sitemap change).
3. **URL inspection** — inspect each URL individually:

| URL | Typical not-indexed reasons to document |
|-----|----------------------------------------|
| `https://georiskengine.com/` | Duplicate host (`www` vs apex), soft 404, blocked by robots |
| `https://georiskengine.com/contact` | 404 before deploy, not in sitemap, discovered but not submitted |
| `https://georiskengine.com/hizmetler` | 404 (page missing), thin content, alternate canonical |

Record GSC reason text verbatim under **Inspection log** (below).

4. **Pages** → Indexing → Pages: compare indexed vs not indexed counts to baseline (1 / 3).
5. **Remind:** indexing can lag 48 hours–2 weeks after deploy and sitemap resubmit.

## Inspection log (fill after each review)

| URL | Date inspected | Coverage status | Reason (from GSC) | Action taken |
|-----|----------------|-----------------|-------------------|--------------|
| `/` | | | | |
| `/contact` | | | | |
| `/hizmetler` | | | | |

## Snapshot — production probe (agent run)

| URL | HTTP (2026-05-25, pre-merge) | Notes |
|-----|------------------------------|-------|
| `https://georiskengine.com/` | 200 | Homepage live |
| `https://georiskengine.com/contact` | 404 | Deploy PR with `contact.html` + rewrite |
| `https://georiskengine.com/hizmetler` | 404 | Deploy `hizmetler.html` + rewrite |
| `https://georiskengine.com/robots.txt` | 404 | Deploy `public/robots.txt` |
| `https://georiskengine.com/sitemap.xml` | 404 | Deploy `public/sitemap.xml` |

Re-run the HTTP table after merge to production and update this section.

## Local build verification

```bash
cd frontend && npm run build && npm run lint
test -f dist/contact.html && test -f dist/sitemap.xml && test -f dist/robots.txt
curl -sS -o /dev/null -w "%{http_code}\n" file://$(pwd)/dist/contact.html  # use static server for path /contact
```

Serve `dist/` with a static server; use `/contact.html` or configure rewrite like Vercel for path `/contact`.
