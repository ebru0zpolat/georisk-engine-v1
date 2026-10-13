# Risk API — hata zarfı

Tüm doğrulama yanıtları aynı JSON zarfını kullanır.

```json
{
  "error": {
    "code": "PRESET_NOT_FOUND",
    "message": "Unknown preset_id; see REGISTERED_PRESET_IDS.",
    "details": {}
  }
}
```

`details` her zaman nesnedir; ek bağlam yoksa `{}`.

Sabitler: `app/core/error_codes.py`. Eşleme: `app/core/validation_errors.py`.

| Kod | HTTP | Anlam |
|-----|------|--------|
| `INVALID_COORDINATES` | 422 | WGS84 dışı lat/lon |
| `INVALID_ASSET` | 422 | Batch satırında eksik id/lat/lon |
| `PRESET_NOT_FOUND` | 422 | Bilinmeyen `preset_id` |
| `INVALID_BATCH` | 422 | Boş `assets` |
| `BATCH_TOO_LARGE` | 422 | `assets` üst sınırı aşıldı |
| `VALIDATION_ERROR` | 422 | Diğer şema hataları |
| `NOT_FOUND` | 404 | Bilinmeyen async `task_id` |
| `TIMEOUT_ERROR` | (batch row) | Satır skor zaman aşımı |
| `INTERNAL_ERROR` | (batch row) | Satır skor hatası |
| `ORAS5_SERIES_UNSCORABLE` | 503 | Live ORAS5 store reachable but this point has no scorable series (land-masked, out of coverage, or too short). |
| `CONNECTOR_STUB_PROHIBITED` | 503 | `APP_ENV=production` refused a connector stub (`_fallback_features`). Configure live Zarr/GEE sources or set `APP_ENV=demo`. |
| `DATA_CENTRE_ASSESS_DISABLED` | 503 | ``POST /v1/risk/data-centre/assess`` is behind ``DATA_CENTRE_ASSESS_ENABLED``. Enabling it never releases downtime or EAL. |
