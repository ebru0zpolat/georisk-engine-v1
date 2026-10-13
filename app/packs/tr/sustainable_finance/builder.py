"""Deterministic evidence-bundle builder + checksum sealing + pack-diff (spec §10).

Given a sealed :class:`EvidencePackInput`, :func:`build_pack` renders the route-scoped file
bundle, computes per-file SHA-256 checksums and a manifest hash, and (when the requested
status is ``reviewer_ready`` or beyond) enforces the claim scan and fail-closed release
gates — refusing to seal if anything blocks.

Determinism contract (spec §16.1): the builder performs no wall-clock reads and no random
draws. The same sealed input reproduces byte-identical files and identical hashes. Any
timestamp comes from ``manifest.generated_at`` supplied by the caller.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.packs.tr.sustainable_finance import regulatory_source as rs
from app.packs.tr.sustainable_finance.claims import ClaimScanResult, PERMITTED_WORDING, scan_bundle
from app.packs.tr.sustainable_finance.gates import ReleaseGateResult, evaluate_release_gates
from app.packs.tr.sustainable_finance.routes import (
    GEORISK_MUST_NOT_PROVIDE,
    ExternalReviewType,
    PackStatus,
    RegulatoryRoute,
)
from app.packs.tr.sustainable_finance.schemas import EvidencePackInput, PackManifest

BUNDLE_ROOT = "tr-sustainable-finance-evidence-pack"
BUILDER_METHODOLOGY_VERSION = "tr-sf-evidence-builder-v0.1"

#: Statuses that require the claim scan + release gates to pass before sealing (spec §12, §13).
_SEALED_STATES = frozenset(
    {
        PackStatus.reviewer_ready,
        PackStatus.issuer_approved,
        PackStatus.second_party_opinion_received,
        PackStatus.verification_received,
    }
)


class PackSealError(RuntimeError):
    """Raised when a pack cannot be sealed to the requested status (fail closed)."""

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons))


def _lifecycle_evidence_problems(pack: EvidencePackInput) -> list[str]:
    """Documentary evidence each post-review lifecycle state requires before sealing (spec §12).

    ``reviewer_ready`` is GeoRisk-assignable and carries no external-evidence requirement.
    Each later state asserts an external event that GeoRisk did not perform, so it must not
    seal on the reviewer_ready gates alone — it needs the matching issuer- or reviewer-
    supplied document:

    * ``issuer_approved`` — a recorded issuer / authorised-body approval reference.
    * ``second_party_opinion_received`` — a recorded second-party-opinion review document.
    * ``verification_received`` — a recorded verification review document.
    """
    manifest = pack.manifest
    status = manifest.status
    review_types = {ref.review_type for ref in pack.external_reviews}
    problems: list[str] = []

    if status is PackStatus.issuer_approved and not (
        manifest.authorised_body_decision_ref and manifest.authorised_body_decision_ref.strip()
    ):
        problems.append(
            "status issuer_approved requires a recorded issuer/authorised-body approval "
            "(authorised_body_decision_ref)"
        )
    if (
        status is PackStatus.second_party_opinion_received
        and ExternalReviewType.second_party_opinion not in review_types
    ):
        problems.append(
            "status second_party_opinion_received requires a recorded second_party_opinion "
            "external-review document"
        )
    if (
        status is PackStatus.verification_received
        and ExternalReviewType.verification not in review_types
    ):
        problems.append(
            "status verification_received requires a recorded verification external-review document"
        )
    return problems


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pretty_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False, default=str)


class BuiltPack:
    """A rendered, checksummed evidence bundle."""

    def __init__(
        self,
        *,
        files: dict[str, str],
        hashes: dict[str, str],
        manifest_sha256: str,
        claim_scan: ClaimScanResult,
        release_result: ReleaseGateResult,
    ) -> None:
        self.files = files
        self.hashes = hashes
        self.manifest_sha256 = manifest_sha256
        self.claim_scan = claim_scan
        self.release_result = release_result

    @property
    def reviewer_ready(self) -> bool:
        return self.release_result.reviewer_ready and self.claim_scan.ok


def _manifest_payload(manifest: PackManifest) -> dict[str, Any]:
    payload = manifest.model_dump(mode="json")
    payload.pop("manifest_sha256", None)  # Hash excludes the slot it fills.
    return payload


def _render_markdown(pack: EvidencePackInput, release: ReleaseGateResult, claim: ClaimScanResult) -> dict[str, str]:
    manifest = pack.manifest
    route = manifest.regulatory_route

    exec_summary = "\n".join(
        [
            f"# TR Sustainable Finance Evidence Pack — {manifest.issuer_legal_name or 'issuer'}",
            "",
            f"- Regulatory route: `{route.value}`",
            f"- Regulatory source: `{manifest.regulatory_source_id}` "
            f"({manifest.regulatory_decision_date}, no. {manifest.regulatory_decision_number})",
            f"- Country pack: `{manifest.country_pack}`",
            f"- Status: `{manifest.status.value}`",
            "",
            "## What this pack is",
            "",
            PERMITTED_WORDING["regulatory_use"] + ". "
            + PERMITTED_WORDING["external_review"] + ".",
            "",
            "## What this pack is not",
            "",
            "GeoRisk does not provide, under the current product contract "
            "(control table — quoted boundary terms):",
            "",
            "| GeoRisk must NOT provide |",
            "| --- |",
            *[f"| {item} |" for item in GEORISK_MUST_NOT_PROVIDE],
            "",
            "## Release status",
            "",
            f"- {release.summary()}",
            f"- {claim.summary()}",
        ]
    )

    route_md = "\n".join(
        [
            "# Regulatory route",
            "",
            f"Selected route: **{route.value}**.",
            "",
            "A use-of-proceeds impact metric is not automatically an eligible "
            "sustainability-linked KPI, and a sustainability-linked KPI does not establish "
            "project eligibility (spec §4).",
        ]
    )

    framework_crosswalk = "\n".join(
        [
            "# Framework crosswalk",
            "",
            "Mandatory components for the selected route:",
            "",
            *[
                f"- `{c}`"
                for c in (
                    rs.USE_OF_PROCEEDS_COMPONENTS
                    if route is RegulatoryRoute.use_of_proceeds
                    else rs.SUSTAINABILITY_LINKED_COMPONENTS
                )
            ],
        ]
    )

    methodology_lines = [
        f"- `{k}` = `{v}`" for k, v in sorted(manifest.methodology_versions.items())
    ] or ["- (none recorded)"]
    methodology_md = "\n".join(
        [
            "# Methodology and assumptions",
            "",
            f"Builder methodology version: `{BUILDER_METHODOLOGY_VERSION}`.",
            "",
            "Methodology versions referenced by this pack:",
            "",
            *methodology_lines,
            "",
            PERMITTED_WORDING["reproducibility"] + ".",
        ]
    )

    limitations_md = "\n".join(
        [
            "# Uncertainty and limitations",
            "",
            pack.uncertainty_and_limitations.strip()
            or "_No uncertainty/limitations text supplied — this pack must not reach reviewer_ready._",
            "",
            "## Physical-risk claim boundary",
            "",
            PERMITTED_WORDING["physical_risk"] + ". "
            + PERMITTED_WORDING["forward_looking"] + ".",
        ]
    )

    recalculation_md_lines = ["# Recalculation policy", ""]
    if pack.recalculation_bridges:
        for bridge in pack.recalculation_bridges:
            recalculation_md_lines.extend(
                [
                    f"## `{bridge.from_methodology_version}` → `{bridge.to_methodology_version}`",
                    "",
                    f"- Reason: {bridge.reason}",
                    f"- Original value: {bridge.original_value}; restated: {bridge.restated_value}; "
                    f"delta: {bridge.delta}",
                    f"- Original run reproducible: {bridge.original_result_reproducible} "
                    f"(run `{bridge.original_run_id}`)",
                    "",
                ]
            )
    else:
        recalculation_md_lines.append(
            "No recalculation bridges in this pack. Historical results must never be silently "
            "overwritten; any model/dataset change is recorded here with a controlled bridge."
        )
    recalculation_md = "\n".join(recalculation_md_lines)

    external_review_md_lines = [
        "# External review index",
        "",
        PERMITTED_WORDING["external_review"] + ".",
        "",
        "| Role | Party |",
        "| --- | --- |",
        f"| framework adviser | {manifest.external_review_roles.framework_adviser or 'not_appointed'} |",
        f"| second-party opinion provider | {manifest.external_review_roles.second_party_opinion_provider or 'not_appointed'} |",
        f"| verifier | {manifest.external_review_roles.verifier or 'not_appointed'} |",
        "",
        "Recorded external-review documents (GeoRisk records the reference; it does not "
        "endorse the conclusion):",
        "",
    ]
    if pack.external_reviews:
        for ref in pack.external_reviews:
            external_review_md_lines.append(
                f"- `{ref.review_type.value}` by {ref.provider_name}: {ref.document_ref}"
            )
    else:
        external_review_md_lines.append("- (none recorded)")
    external_review_md = "\n".join(external_review_md_lines)

    perf_crosswalk = "\n".join(
        [
            "# Performance / reporting crosswalk",
            "",
            "Use-of-proceeds: allocation report (annual until full allocation), material "
            f"update within {rs.MATERIAL_DEVELOPMENT_MAX_WEEKS} weeks, final report + mandatory "
            f"verification within {rs.FINAL_REPORTING_MAX_MONTHS_AFTER_FULL_ALLOCATION} months of "
            "full allocation; impact report within the same window (external review optional).",
            "",
            "Sustainability-linked: performance report at least annually; mandatory independent "
            "verification of KPI performance against each SPT (limited or reasonable assurance).",
        ]
    )

    return {
        "executive-summary.md": exec_summary,
        "regulatory-route.md": route_md,
        "framework-crosswalk.md": framework_crosswalk,
        "methodology-and-assumptions.md": methodology_md,
        "uncertainty-and-limitations.md": limitations_md,
        "recalculation-policy.md": recalculation_md,
        "external-review-index.md": external_review_md,
        "performance-report-crosswalk.md": perf_crosswalk,
    }


def _render_json_files(pack: EvidencePackInput, manifest_json: dict[str, Any]) -> dict[str, str]:
    manifest = pack.manifest
    route = manifest.regulatory_route
    files: dict[str, str] = {}

    files["manifest.json"] = _pretty_json(manifest_json)
    files["responsibility-matrix.json"] = _pretty_json(
        [r.model_dump(mode="json") for r in manifest.responsibility_map]
    )
    files["claims-register.json"] = _pretty_json(pack.claims.model_dump(mode="json"))
    files["data-lineage.json"] = _pretty_json(
        [p.model_dump(mode="json") for p in pack.provenance]
    )

    if route is RegulatoryRoute.use_of_proceeds:
        files["project-register.json"] = _pretty_json(
            [p.model_dump(mode="json") for p in pack.projects]
        )
        files["impact-metrics.json"] = _pretty_json(
            [m.model_dump(mode="json") for m in pack.impact_metrics]
        )
        if pack.proceeds_interface is not None:
            files["proceeds-data-interface.json"] = _pretty_json(
                pack.proceeds_interface.model_dump(mode="json")
            )
    elif route is RegulatoryRoute.sustainability_linked:
        files["kpi-register.json"] = _pretty_json(
            [k.model_dump(mode="json") for k in pack.kpis]
        )
        files["spt-register.json"] = _pretty_json(
            [s.model_dump(mode="json") for s in pack.spts]
        )
        files["instrument-effects.json"] = _pretty_json(
            [e.model_dump(mode="json") for e in pack.instrument_effects]
        )

    # Audit sub-bundle.
    files["audit/run-index.json"] = _pretty_json(
        {
            "analysis_run_ids": list(manifest.analysis_run_ids),
            "provenance_run_ids": sorted({p.analysis_run_id for p in pack.provenance}),
            "methodology_versions": dict(sorted(manifest.methodology_versions.items())),
        }
    )
    files["audit/change-log.json"] = _pretty_json(
        [b.model_dump(mode="json") for b in pack.recalculation_bridges]
    )
    return files


def build_pack(pack: EvidencePackInput) -> BuiltPack:
    """Render, checksum and (when sealing) gate a route-scoped evidence bundle (spec §10)."""
    manifest = pack.manifest

    # 1. Evaluate gates + claim scan first (needed for the executive summary + sealing).
    release_result = evaluate_release_gates(pack)

    # 2. Compute the manifest hash over the canonical manifest (excluding its own hash slot).
    manifest_payload = _manifest_payload(manifest)
    manifest_sha256 = _sha256_hex(_canonical_json(manifest_payload))
    manifest_json = dict(manifest_payload)
    manifest_json["manifest_sha256"] = manifest_sha256

    # 3. Render all files (markdown first so the claim scan can see them).
    md_files = _render_markdown(pack, release_result, ClaimScanResult())
    json_files = _render_json_files(pack, manifest_json)

    # 4. Claim scan over the rendered markdown + JSON bodies.
    scannable = {**md_files, **json_files}
    claim_scan = scan_bundle(scannable)

    # Re-render the executive summary now that the claim scan result is known.
    md_files = _render_markdown(pack, release_result, claim_scan)
    files: dict[str, str] = {**md_files, **json_files}

    # 5. Per-file checksums (exclude hashes.sha256 itself), sorted for determinism.
    hashes = {name: _sha256_hex(body) for name, body in sorted(files.items())}
    hashes_body = "\n".join(f"{digest}  {name}" for name, digest in hashes.items()) + "\n"
    files["audit/hashes.sha256"] = hashes_body

    built = BuiltPack(
        files=files,
        hashes=hashes,
        manifest_sha256=manifest_sha256,
        claim_scan=claim_scan,
        release_result=release_result,
    )

    # 6. Fail closed when sealing to reviewer_ready or beyond. Post-review states additionally
    #    require their matching issuer/reviewer evidence document (spec §12).
    if manifest.status in _SEALED_STATES:
        lifecycle_problems = _lifecycle_evidence_problems(pack)
        if not built.reviewer_ready or lifecycle_problems:
            reasons = list(release_result.blocking_reasons)
            if not claim_scan.ok:
                reasons.append(claim_scan.summary())
            reasons.extend(lifecycle_problems)
            raise PackSealError(reasons)

    return built


def pack_diff(old: dict[str, str], new: dict[str, str]) -> dict[str, list[str]]:
    """Diff two ``{filename: sha256}`` maps (spec §10 pack-diff / audit change tracking)."""
    old_names = set(old)
    new_names = set(new)
    added = sorted(new_names - old_names)
    removed = sorted(old_names - new_names)
    changed = sorted(n for n in old_names & new_names if old[n] != new[n])
    return {"added": added, "removed": removed, "changed": changed}


__all__ = [
    "BUILDER_METHODOLOGY_VERSION",
    "BUNDLE_ROOT",
    "BuiltPack",
    "PackSealError",
    "build_pack",
    "pack_diff",
]
