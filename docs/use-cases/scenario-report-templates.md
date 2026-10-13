# Scenario scorecard report templates (A / B / C)

Consumer rules for `scenario_scoring` fields (GEO-152 / GEO-153). DeerFlow **must not** call `derive_confidence()` or recompute scores.

---

## Template A — Full diligence appendix

**Required sections**

1. Executive line: baseline vs scenario scores (not raw multipliers alone).
2. **Per-driver multiplier table** from `hazard_driver_multipliers` (e.g. pluvial_flood 1.30, drought_stress 1.35).
3. Single row: `hazard_multiplier` with label **weighted_effective** (`hazard_multiplier_type`).
4. `coefficient_table_version` + `coefficient_table_hash` footer.
5. `confidence` + bullet list from `confidence_reasons`.
6. If `scenario_delta_pct` is `null`, display **N/A** (baseline zero).

---

## Template B — Investor one-pager

**Required**

- Headline: `baseline_score` → `scenario_score` (`scenario_delta_points` points).
- **One-line note** for multiplier: “Hazard-weighted effective uplift {hazard_multiplier}× (drivers: …).”
- Do **not** show a full driver table (Template A only).
- If `confidence` is **low**: **amber banner** mandatory — cite `confidence_reasons`.
- If `scenario_delta_pct` is `null`: **omit** the percent row entirely.

---

## Template C — Committee brief

**Required**

- Decision signal block (scores, spread, primary `drivers`).
- **Explicit disclosure** when `confidence` is low (quote `confidence_reasons`).
- `coefficient_table_hash` visible for audit trail.
- `scenario_delta_pct` null → **N/A** in table.

---

## DeerFlow boundary

| Allowed | Forbidden |
|---------|-----------|
| Format MCP `scenario_scoring` JSON | `derive_confidence()` in agent code |
| Narrate `propagation` / `hazard_results` | Change `hazard_multiplier` math |
| Propose coefficient table PRs | Merge coefficients without CI hash bump |
