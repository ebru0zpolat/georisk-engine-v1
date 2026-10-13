# Landing page map (`frontend/index.html`)

**Last audited:** 2026-09-01

> Replaces `APP_TSX_MAP.md`. That document described `frontend/src/App.tsx` as the
> landing page mounted by Vite. It was not: nothing imported `App.tsx`, and
> `vite.config.ts` only ever built `index.html` and `contact.html`. The file has
> been removed; this document describes the page that actually ships.

---

## What serves what

| URL | Served by | Notes |
|-----|-----------|-------|
| `/` | `frontend/index.html` | Static marketing landing. Content is in the first HTML response — no JS needed to read it. |
| `/hizmetler`, `/services`, `/methodology`, `/blog/*`, and the fan-out pages | `frontend/public/<path>/index.html` | Static, each with its own canonical + JSON-LD. |
| `/demo`, `/tiles`, `/snapshot/:assetId` | React, via `src/main.tsx` | `body.spa-app` hides the static landing so `#root` owns the viewport. |
| `/contact` | `frontend/contact.html` | Second Vite build input. |

`src/main.tsx` mounts **only** the three SPA routes above. There is no React
component for `/`.

---

## `index.html` structure

| Zone | Notes |
|------|-------|
| `<style>` | The whole page's CSS, including bare `nav` / `section` element rules. **These are global** — React markup rendered into this shell inherits them. |
| `.site-header` | Fixed stack: `<nav>`, the ≤1024px menu sheet, and the claim strip. Its measured height is published as `--header-h`; `#hero` and `scroll-padding-top` both read it. |
| `.claim-strip` | Fail-closed strip. States `decision = demo_only · production_eligible = false`. Never hidden at any width. |
| `#hero` | Headline, CTAs, and the coordinate box. The box is bound by `src/heroScorecard.ts` (see below). |
| `#platform`, `#demo`, `#usecases`, `#data`, `#api`, `#docs`, `#pricing`, `#cta` | Static marketing sections. `#demo` is a **pinned sample**, labelled `FIXTURE`, not a live call. |
| `#claims` | Claim-control vocabulary: nine states, their glyphs and their wording. |
| `#evidence` | Source manifest, hash-chain description, limitations, and the release gates. Gate states mirror `app/services/release_manifest.py` — update both together. |
| inline `<script>` | Ticker, reveal-on-scroll, nav scroll effect, mobile menu toggle, `--header-h` measurement. |

### Claim chips

`.claim-chip[data-claim-state="…"]` — nine states, styled in `index.html`. The
wording (glyph, label, tooltip) lives in `src/claimStates.ts` so the static page
and the TypeScript modules stay in sync. A chip is never rendered below 8.5px
and never without its label.

**Rule:** a chip states what the value behind it can support. Do not upgrade a
value to `VERIFIED` or `LIVE` because a call succeeded — the endpoint has to say
so.

---

## The hero scorecard (UC-01)

`src/heroScorecard.ts` binds `#heroInput` / `#heroSubmit` to
`computePreviewRiskScore()` → `POST /v1/risk/preview`.

- It self-guards: returns early on `body.spa-app`, and if the elements are absent.
- The endpoint returns an indicative composite over climate and satellite proxies
  and **does not report a per-component claim state**, so every value it renders
  is labelled `MODELLED`, and the endpoint's own `disclaimer` is printed verbatim
  beside the score.
- Failures render the error. There is no simulated progress.

**API base:** `VITE_API_BASE_URL`, else the public demo host in production, else
`localhost:8002/v1` in dev. Set `VITE_API_BASE_URL` in Vercel — `/demo` needs it
too (see `docs/08-ops/API_DEPLOY.md`).

---

## Breakpoints

`1520px` (nav sheds lower-priority links), `1024px` (links → menu sheet; claim
list 3-up → 2-up; evidence stacks), `768px` (everything 1-up), `400px` (nav
padding, CTA padding and logo type step down so logo + CTA + menu button clear
each other at the 320px floor).

The Request Demo CTA stays in the bar at **every** width; only the links collapse.

---

## Guardrails

`frontend/scripts/verify-public-assets.mjs` runs in CI and enforces, among other
things: required strings and forbidden compliance wording per page, minimum
English keyword densities on `/hizmetler` and `/services`, canonical + breadcrumb
JSON-LD, and that `/hizmetler` stays **out** of `sitemap.xml`. Read it before
editing marketing copy — several phrasings are load-bearing.
