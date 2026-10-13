"""SHA-bound artifact manifests with deterministic checksums."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from pathlib import PurePosixPath
from typing import Iterable, Literal

from pydantic import Field, model_validator

from app.automation.models import CheckResult, StrictModel


class ArtifactFile(StrictModel):
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)


class ArtifactManifest(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    workflow_run_id: str = Field(min_length=1)
    generated_at: datetime
    evidence_kind: Literal["ci"] = "ci"
    artifact_type: Literal["founder_digest", "pr_classification"]
    checks_observed: list[CheckResult]
    files: list[ArtifactFile]

    @model_validator(mode="after")
    def exact_sha(self) -> "ArtifactManifest":
        if any(item.commit_sha != self.commit_sha or item.evidence_kind != "ci" for item in self.checks_observed):
            raise ValueError("artifact checks must be CI evidence for the manifest exact SHA")
        paths = [item.path for item in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("artifact manifest contains duplicate file entries")
        for path in paths:
            candidate = PurePosixPath(path)
            if candidate.is_absolute() or ".." in candidate.parts or len(candidate.parts) != 1:
                raise ValueError("artifact manifest path is unsafe")
        return self


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    *, directory: Path, filenames: list[str], commit_sha: str, workflow_run_id: str,
    generated_at: datetime, checks_observed: list[CheckResult], artifact_type: str = "pr_classification",
) -> ArtifactManifest:
    files = []
    for name in sorted(filenames):
        target = directory / name
        files.append(ArtifactFile(path=name, sha256=sha256_file(target), size_bytes=target.stat().st_size))
    return ArtifactManifest(
        commit_sha=commit_sha, workflow_run_id=workflow_run_id, generated_at=generated_at,
        checks_observed=checks_observed, files=files, artifact_type=artifact_type,
    )


def missing_required_checks(checks: Iterable[CheckResult], required: set[str], sha: str) -> list[str]:
    """Return, sorted, the required check names that did not pass at `sha`."""
    passing = {item.name for item in checks if item.state == "pass" and item.commit_sha == sha}
    return sorted(required - passing)


def verify_manifest(
    manifest: ArtifactManifest, directory: Path, expected_sha: str, *,
    expected_run_id: str | None = None, expected_type: str | None = None,
    expected_files: set[str] | None = None, required_checks: set[str] | None = None,
) -> None:
    if manifest.commit_sha != expected_sha:
        raise ValueError("stale or wrong-SHA artifact")
    if expected_run_id is not None and manifest.workflow_run_id != expected_run_id:
        raise ValueError("artifact workflow run ID mismatch")
    if expected_type is not None and manifest.artifact_type != expected_type:
        raise ValueError("artifact type mismatch")
    manifest_files = {item.path for item in manifest.files}
    if expected_files is not None and manifest_files != expected_files:
        raise ValueError("artifact file inventory mismatch")
    actual_files: set[str] = set()
    for target in directory.iterdir():
        if target.is_symlink():
            raise ValueError("artifact directory contains a symlink")
        if not target.is_file():
            raise ValueError("artifact directory contains an unexpected non-file")
        actual_files.add(target.name)
    if actual_files != manifest_files | {"manifest.json"}:
        raise ValueError("artifact directory has missing or unexpected files")
    if required_checks is not None:
        missing = missing_required_checks(manifest.checks_observed, required_checks, expected_sha)
        if missing:
            raise ValueError(f"artifact required-check provenance is incomplete: not passing at {expected_sha}: {', '.join(missing)}")
    for item in manifest.files:
        target = directory / item.path
        if target.is_symlink() or not target.is_file() or target.stat().st_size != item.size_bytes or sha256_file(target) != item.sha256:
            raise ValueError(f"artifact checksum mismatch: {item.path}")


def write_manifest(manifest: ArtifactManifest, path: Path) -> None:
    path.write_text(json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")
