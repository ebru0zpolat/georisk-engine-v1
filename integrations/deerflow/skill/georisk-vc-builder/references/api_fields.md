# GeoRisk API → VC memo fields

Maps `POST /v1/risk/score` response (`RiskScoreResponse`) to memo bullets.

| Memo use | JSON path | Notes |
|----------|-----------|--------|
| Headline score | `overall_score` | 0–100 |
| Risk band | `risk_band` | e.g. low / moderate / high |
| One-line read | `interpretation` | Plain-language summary |
| Industrial activity | `components.industrial` | Component 0–100 |
| Pollution proxies | `components.pollution` | |
| Land | `components.land` | |
| Ocean / climate | `components.ocean` | See also `ocean_features` |
| Agriculture | `components.agriculture` | |
| Sensitivity | `components.sensitivity` | |
| Flags | `flags` | List of strings |
| Ocean detail | `ocean_features` | SST, sea level, etc. |
| GEE proxies | `gee_features` | Night lights, NO₂, NDVI stubs |
| Baseline | `gee_baseline` | When present |
| Audit trail | `audit_id`, `generated_at` | Cite in memo footer |
| Operational cross-check | `industrial_verification` | When `include_industrial_verification_ref` true |
| Linked audit | `industrial_verification.linked_audit_id` | Must equal `audit_id` |
| Nearest facility | `industrial_verification.nearest_primary_audit` | May be null |

Full narrative: use Markdown from `georisk_report_markdown` tool (not re-derived from JSON).
