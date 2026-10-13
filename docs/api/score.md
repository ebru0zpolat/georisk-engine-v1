# Tekil risk skoru — `POST /v1/risk/score`

**Şema:** `app/schemas/risk.py` (`RiskScoreRequest` → `RiskScoreResponse`).

## Dual-publish yanıt

| Alan | Tip | Not |
|------|-----|-----|
| `overall_score` | int 0–100 | Altı bileşen ortalaması (legacy; kırılmaz) |
| `components` | object | industrial…sensitivity (+ flood/heat scaffold) |
| `risk_score` | float 0–1 | Preset-weighted compound |
| `scores.{heat,water_stress,climate}` | float 0–1 | Compound drivers |
| `confidence` | float 0–1 | Driver spread |
| `preset_id` | string | `REGISTERED_PRESET_IDS` |
| `meta.updated_at` | datetime | Skor bitiş UTC |
| `location.{lat,lon}` | computed | Koordinat echo |

## `preset_id`

Kayıt: `app/core/preset_registry.py` — `industrial_v1` (default), `agriculture_v1`, `transformer_v1`.  
Bilinmeyen → **422** `PRESET_NOT_FOUND`.

## `GET /v1/risk/score`

Zorunlu: `lat`, `lon`. İsteğe bağlı: `preset_id` (default `industrial_v1`), `asset_name`, `sector`, `radius_km`, `include_industrial_verification_ref`.

```bash
curl -sS "http://127.0.0.1:8002/v1/risk/score?lat=41.02&lon=29.01&preset_id=industrial_v1"
```

## `POST` örnek

```bash
curl -sS -X POST "http://127.0.0.1:8002/v1/risk/score" \
  -H "Content-Type: application/json" \
  -d '{"asset_name":"TR-001","latitude":41.02,"longitude":29.01,"preset_id":"industrial_v1"}'
```

Hata zarfı: [`errors.md`](./errors.md). Batch: [`batch.md`](./batch.md).
