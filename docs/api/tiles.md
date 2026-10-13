# Risk tiles — `GET /v1/tiles/{layer}/{z}/{x}/{y}.png`

Blueprint-aligned PNG tiles for the **Marmara pilot** bbox (Sprint 5).

## Layers

| `layer` | Meaning |
|---------|---------|
| `total_risk` | `climate*0.6 + water*0.4` (deterministic pilot field) |
| `climate` | Climate sub-field |
| `water` | Water-stress sub-field |

## Example

```bash
curl -sS -o tile.png "http://127.0.0.1:8002/v1/tiles/total_risk/6/37/23.png"
```

Tiles outside the pilot return a transparent PNG (HTTP 200). Zoom 0–12.

**Not yet:** CDN cache, live CDS raster ingest, deck.gl client wiring.
