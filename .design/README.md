# Design canvas sources

Artboard sources for the MVP P0 design canvas. Each `.dc.html` is one artboard;
`canvas.json` is the layout. Requirements they implement:
[`docs/03-frontend/MVP_P0_DESIGN_REQUIREMENTS.md`](../docs/03-frontend/MVP_P0_DESIGN_REQUIREMENTS.md).

| File | Deliverable |
|---|---|
| `Main.dc.html` | P0-3 — portfolio upload, column mapping, excluded-asset triage |
| `AssetDetail.dc.html` | P0-4 — five-layer waterfall, horizon, location context |
| `EvidenceViewer.dc.html` | P0-2 — audit identity, integrity, source manifest, limitations |
| `TrustChips.dc.html` | P0-1 — chip anatomy and state dictionary |
| `Tokens.dc.html` | P0-5 — colors, risk bands, type ramp, number formats, state patterns |
| `MobileSnapshot.dc.html` | Mobile 390×844 — read-only asset snapshot with a horizon switch |
| `MobileTriage.dc.html` | Mobile 390×844 — field triage: capture location, add photo, confirm, next |

Colors and type come from the `frontend/src/index.css` token scale: ink ground,
three signal families (teal `#2ec990`/`#5dcaa5`, amber `#ef9f27`, red `#e24b4a`)
plus a neutral pair, Inter with 800 headings at `-0.02em`. No fourth hue is opened —
the risk band scale reuses the same three families. All figures in the screens are
sample values, not engine output.

The chip dictionary is nine states across those four families, split over two axes:
`VERIFIED / LIVE / FIXTURE / SYNTHETIC` answer where the input came from, while
`MODELLED / DERIVED / STALE` answer how far the value sits from its input and how old
it is. They occupy separate slots — a value can be both `LIVE` and `STALE`. `STALE`
carries an age affix (`STALE · 14d`) because its container treatment alone does not
survive a downscaled screenshot.

The two mobile artboards are responsive-web targets, not native apps: the only
genuinely mobile workflows are glancing at an asset and fixing a geocode failure
on site. Neither draws OS chrome (status bar, keyboard).

Every artboard except `Tokens.dc.html` is a working prototype — artboards cannot
link to each other, so each flow runs inside its own frame.

The published canvas is regenerated from these files — the seeded output is
gitignored.
