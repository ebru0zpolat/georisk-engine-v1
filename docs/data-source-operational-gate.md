# `data_source_operational` gate

> The fail-closed readiness gate for the production state `data_source_operational`
> (roadmap §1). Advances P2 (credentialed connectors) with the same discipline
> the Stage 5 real-event validation gate (roadmap §Stage 5; GEO-105 closed as the
> self-attested MVP tier on 2026-08-31 and no longer carries it) applies to
> `model_validated_for_use_case`.

## Why

The registry + `delivery_mode_for` already track whether a connector is wired to
**live** credentials (vs fallback/mock/stub). That is necessary but **not
sufficient**. The roadmap defines `data_source_operational` as a connector with a
**verified licence, live runtime evidence, provenance, and retention controls** —
four controls, not just "credentials present".

`app/core/data_source_operational_gate.py` turns those four into a fail-closed
verdict. A source is `operational=True` only when **all** hold:

1. `delivery_mode == "live"` (real credentials configured);
2. a commercial-use **licence** on file and in effect (`LicenceRecord`);
3. a recent **live-runtime evidence** sample from a real live call, fingerprinted
   (`LiveRuntimeEvidence`, `sample_sha256`, `delivery_mode="live"`);
4. a **retention** policy declared (`RetentionPolicy`, positive horizon + storage).

Any gap → `operational=False` with the reason named. A connector that merely
*could* run live but has no licence, no captured live evidence, or no retention
policy is **not** operational.

## Usage

```python
from app.core.data_source_operational_gate import evaluate_data_source_operational
verdict = evaluate_data_source_operational(
    source_id="gee_viirs_ntl", delivery_mode="live",
    licence=..., live_evidence=[...], retention=..., as_of=date.today())
```

Registry-wide (fail-closed for sources with no records):

```bash
PYTHONPATH=. python scripts/run_data_source_operational_demo.py
```

In an env with no credentials/records, every source reads not-operational — the
honest state. The demo names, per source, which control is missing.

## Records source (wired to the real connectors)

The three record controls come from `app/core/data_source_operational_records.py`:

- **Licence + retention** — declared in `config/data_source_operational.json`
  (empty by default → fail-closed; fill from `…example.json` when a licence
  lands). Legal facts, never inferred.
- **Live-runtime evidence** — appended to `data/operational/live_evidence.jsonl`
  by `scripts/capture_live_evidence.py`, which **drives the real connectors**
  (`CDSOras5Connector` / `GeeConnector`) for each live-configured source and
  fingerprints the connector's live output (`capture_live_evidence` — SHA-256 of
  the returned features). Only a `live` delivery is recorded; a fallback/stub
  fetch is never evidence.

`OperationalRecordsStore().verdicts(delivery_mode_by_source)` combines all three
with `delivery_mode_for` to produce the per-source verdicts. In an env with no
credentials, `capture_live_evidence.py` records nothing and the gate stays
fail-closed — the honest state.

## Provisioning a source (the single command)

`scripts/provision_operational_source.py` is the validated operator command for
populating the four controls "as keys become available". It **never fabricates a
control** — it validates, reports what is missing, and (with `--capture`) drives
the real connector to record live evidence.

```bash
# Show the four-control checklist for every credentialed source, with the exact
# next action per gap (validates the config first — a typo'd source_id fails LOUD
# here instead of becoming a permanent silent fail-closed):
PYTHONPATH=. python scripts/provision_operational_source.py

# One source; once its credentials are configured, capture live evidence too:
PYTHONPATH=. python scripts/provision_operational_source.py --source oras5_ocean --capture
```

Under the hood:

- `validate_operational_config(...)` cross-checks `config/data_source_operational.json`
  against the registry ids and flags unknown/typo'd source ids, duplicates,
  unparseable dates, non-commercial licences, and non-positive retention — the
  mistakes that would otherwise be indistinguishable from "no licence".
- `provisioning_status(...)` composes the gate verdict into a per-control
  checklist with next actions (`OperationalRecordsStore.provisioning(...)` runs it
  registry-wide). It reuses `evaluate_data_source_operational` — no logic is
  duplicated, so the checklist can never disagree with the gate.

## What P2 still needs to flip a source operational

For each credentialed source (CDS ERA5, GEE VIIRS/S5P, Copernicus Marine ORAS5),
`provision_operational_source.py` names exactly which of these is outstanding:

1. Configure live credentials so `delivery_mode_for` returns `live` (free
   accounts/keys; egress to the provider). The checklist prints the env var to set.
2. File a `LicenceRecord` in `config/data_source_operational.json`.
3. Capture live evidence: `--capture` (or `scripts/capture_live_evidence.py`)
   drives the real connector and appends a fingerprinted record.
4. Declare a `RetentionPolicy` in the same config.

Only then does the gate return `operational=True`. The records seam is
deliberately explicit so operational status is evidence-backed, never inferred
from "the connector didn't error".
