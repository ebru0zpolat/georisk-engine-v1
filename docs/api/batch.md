# Risk batch API

## Endpoints

| Method | Path | Notes |
|--------|------|--------|
| `POST` | `/v1/risk/batch` | Sync; max **500** assets; partial success |
| `POST` | `/v1/risk/batch/async` | PoC **202** + `task_id` (max **5000**, chunk 500) |
| `GET` | `/v1/risk/batch/status/{task_id}` | PoC status + `result` when COMPLETED |

## Sync example

```bash
curl -sS -X POST "http://127.0.0.1:8002/v1/risk/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "preset_id": "industrial_v1",
    "sector": "industrial",
    "assets": [
      {"id": "TR-001", "lat": 41.02, "lon": 29.01},
      {"id": "TR-002", "lat": 39.93, "lon": 32.85}
    ]
  }'
```

Kısmi başarı: geçersiz koordinat satırı tüm isteği düşürmez; `summary.success_count` / `failed_count` + satır `error`.

## Async

```bash
curl -sS -X POST "http://127.0.0.1:8002/v1/risk/batch/async" \
  -H "Content-Type: application/json" \
  -d '{"preset_id":"industrial_v1","assets":[{"id":"A","lat":41.0,"lon":29.0}]}'
# → {"task_id":"...","status_path":"/v1/risk/batch/status/..."}
```

### Üretim modu: Redis/Celery

`REDIS_URL` ayarlandığında (`redis://host:6379/0`):

- `POST /v1/risk/batch/async` görevi **Celery** kuyruğuna atar (`georisk.risk_batch_score`).
- Görev durumu paylaşımlı **Redis** store'da tutulur (`georisk:async_batch:{task_id}`, TTL 24 saat) — status endpoint'i herhangi bir API sürecinden okur.
- Worker başlatma:

```bash
REDIS_URL=redis://localhost:6379/0 celery -A app.workers.celery_app:celery_app worker --loglevel=info
```

`REDIS_URL` yoksa in-process BackgroundTasks yolu ve in-memory store devrede kalır (CI / lokal, altyapısız).

## Performans notu

Batch prefetch, spatial-cell coalesce üzerinden **bulk** connector çağrıları kullanır:

- **ORAS5:** tüm hücre temsilcileri tek vektörize `ds.sel` ile Zarr store'dan tek seferde okunur.
- **GEE:** tüm hücreler tek `reduceRegions` RPC'sinde (band/pencere başına bir çağrı) toplanır.

Kimlik bilgisi yokken her iki connector deterministik fallback döndürür (offline CI güvenli).
