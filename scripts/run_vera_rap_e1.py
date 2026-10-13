"""Run the deterministic Experiment E1 pilot with fixture baselines and VERA-RAP.

Usage: PYTHONPATH=. python scripts/run_vera_rap_e1.py [--per-bucket N] [--out path]
Research-only; no network, no model calls, no production code paths.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from benchmarks.vera_rap import load_benchmark_cases
from experiments.vera_rap import (
    build_default_systems,
    build_e1_case_set,
    build_e1_config,
    build_e1_manifest,
    comparison_summary,
    default_system_configs,
    load_fixture_generators,
    run_e1_experiment,
)

EVALUATION_TIME = datetime(2026, 3, 1, tzinfo=UTC)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-bucket", type=int, default=1)
    parser.add_argument("--baseline-fixture", default="baseline-confident")
    parser.add_argument("--rag-fixture", default="rag-insufficiency-aware")
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    pairs = build_e1_case_set(load_benchmark_cases(), per_bucket=args.per_bucket)
    configs = default_system_configs()
    generators = load_fixture_generators()
    systems = build_default_systems(
        configs,
        baseline_generator=generators[args.baseline_fixture],
        rag_generator=generators[args.rag_fixture],
        retrieved_at=EVALUATION_TIME,
    )
    config = build_e1_config(
        pairs,
        configs,
        evaluation_timestamp=EVALUATION_TIME,
        repetitions=args.repetitions,
    )
    manifest = build_e1_manifest(config, created_at=EVALUATION_TIME)
    result = run_e1_experiment(
        config,
        pairs,
        (),
        systems,
        metadata={
            "label": "OFFLINE FIXTURE PILOT",
            "note": "Infrastructure validation with scripted fixture baselines; not evidence about commercial LLM providers.",
            "baseline_fixture": args.baseline_fixture,
            "rag_fixture": args.rag_fixture,
        },
    )
    print(json.dumps(comparison_summary(result.comparisons), indent=2, sort_keys=True))
    print(f"manifest_fingerprint={manifest.fingerprint}")
    print(f"run_fingerprint={result.fingerprint}")
    if args.out is not None:
        args.out.write_text(result.canonical_json() + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
