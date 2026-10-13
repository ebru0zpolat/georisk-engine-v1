# Gate-1 scientific-validation harness

Shell for **criterion 1.4** of [`docs/business/SIX_MONTH_VALIDATION_GATES.md`](../../../docs/business/SIX_MONTH_VALIDATION_GATES.md):
evaluate the model and a named naive baseline on the same sample under the same
information cutoff, against a pre-registered success rule.

## What's here

| File | Role |
|------|------|
| `pre_registration.py` | Machine-readable, content-hashed study params (companion to the human [template](../../../docs/business/gate1_pre_registration_TEMPLATE.md)). Refuses to run unless frozen and rejects post-freeze payload changes. |
| `observed_loss.py` | `SampleUnit` + `ObservedLossProvider` seam. Default provider is **fail-closed** — no licensed data, no run. The provider contract includes `is_synthetic: bool` — a real integration **must** set it `False` (fixtures set `True`); it is read fail-closed (`getattr(..., True)`), stamped onto the report, and a synthetic dataset can never validate. |
| `baselines.py` | Named, cutoff-safe naive baselines (`zero_loss`, `prior_mean`, `value_fraction`, and source-hashed `historical_coverage_ratio`). |
| `metrics.py` | `mae`, `rmse`. |
| `model_adapter.py` | `ExpectedLossModelAdapter` — wraps `compute_expected_loss`; blocks lookahead; isolated audit trail. |
| `harness.py` | `run_comparison(...)` — the orchestrator. |
| `report.py` | Deterministic `ComparisonReport` with a config hash. |
| `model_validation_gate.py` | The `model_validated_for_use_case` verdict (tiered): report **passed** is necessary but not sufficient — an attestation bound to the study's `config_hash` on a non-synthetic dataset is also required. |

Runnable entry points: [`scripts/run_gate1_comparison.py`](../../../scripts/run_gate1_comparison.py) (the study) and [`scripts/run_gate1_validation_gate_demo.py`](../../../scripts/run_gate1_validation_gate_demo.py) (gate mechanics on a labelled fixture).
Seal a committed draft with `python scripts/freeze_gate1_preregistration.py PATH`;
after committing the sealed file, audit it with the same command plus `--verify`.
The freeze commit must contain the exact scientific payload, while the stored
SHA-256 makes later changes fail closed without relying on a boolean flag.

## `passed` is not `validated` (tiered)

`run_comparison` answers *did the model beat the pre-registered baseline on
licensed data?* — stamped as `report.passed`. The production readiness state
`model_validated_for_use_case` needs more. `evaluate_model_validation(report,
reviewer, minimum_tier=…)` returns `validated=True` **only** when all hold:

1. `report.passed` under the frozen success rule;
2. the observed-loss dataset is **not** synthetic/placeholder
   (`SYNTHETIC_DATASET_NAMES`);
3. a reviewer **approved**, with `attested_config_hash == report.config_hash`,
   at a tier meeting `minimum_tier`.

**Tiers** (external review isn't available pre-funding, so validation is
tiered, not all-or-nothing):

- `self_attested` — the author/team signs off (same org). **The MVP default
  minimum**: honest, auditable, achievable solo.
- `independent` — an external reviewer from a different org signs off. The
  higher-assurance tier, unlocked later.

The verdict always names the achieved `tier`, so "validated (self-attested)"
never reads as independent assurance. Fail-closed: any gap leaves
`validated=False` with the reason named. A mechanics run on fixture data can
pass the comparison yet never validates at **any** tier — a signature cannot
rescue a synthetic dataset (denylist). The v0.4 depth/JRC model (P1) is
validated through `ExpectedLossModelAdapter(..., depth_catalogue=...)`, which
prices flood from inundation depth per unit.

## Why it refuses to run today

By design, so no result is ever produced on synthetic or unlicensed data. Two
guards must be cleared first — both are human Gate-1 blockers:

1. **Freeze the pre-registration (criterion 1.2).** Copy
   `pre_registration.example.json`, fill it in, set `frozen: true` with a
   `freeze_timestamp` and `freeze_commit`. The harness raises
   `PreRegistrationNotFrozen` otherwise.
2. **Wire a licensed observed-loss provider (criterion 1.3).** Implement
   `ObservedLossProvider` over your licensed dataset and swap it in for
   `UnlicensedObservedLossProvider` in the script. The harness raises
   `ObservedLossDataUnavailable` otherwise.

Once both are cleared, the sample is checked for lookahead (every unit's
`features_as_of` must be ≤ the cutoff), model and baseline predict on the
identical sample, and the report records the pass/fail against the frozen
success rule.

## Tests

`tests/validation/test_gate1_harness.py` — structural tests with in-memory
fakes (not a validation result). Run: `python3 -m pytest tests/validation -q`.
