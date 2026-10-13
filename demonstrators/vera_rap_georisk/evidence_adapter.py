"""Read-only conversion of fixture records to canonical RAP-001 evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Mapping

from app.research.vera_rap import (
    EvidenceObject,
    Provenance,
    Uncertainty,
    VerificationStatus,
)
from .models import GeoRiskEvidenceType


def _time(value: str | None) -> datetime | None:
    return (
        None if value is None else datetime.fromisoformat(value.replace("Z", "+00:00"))
    )


class GeoRiskEvidenceAdapter:
    """Adapter with no provider access and no trust based on source branding."""

    def convert(
        self, item: Mapping[str, Any], *, evaluation_time: datetime
    ) -> EvidenceObject:
        content = item.get("content", {"value": item.get("value")})
        digest = (
            item.get("content_fingerprint")
            or hashlib.sha256(
                json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        )
        provenance_data = item.get("provenance") or {}
        provenance_complete = all(
            provenance_data.get(k) for k in ("source_identifier", "retrieval_mechanism")
        )
        valid_until = _time(item.get("valid_until"))
        status = VerificationStatus[item.get("verification_status", "VERIFIED")]
        if not provenance_complete or not item.get("content_fingerprint"):
            status = VerificationStatus.REJECTED
        elif valid_until and evaluation_time > valid_until:
            status = VerificationStatus.STALE
        elif item.get("valid_transformation") is False:
            status = VerificationStatus.REJECTED
        return EvidenceObject(
            evidence_id=item["evidence_id"],
            evidence_type=GeoRiskEvidenceType(item["evidence_type"]).value,
            source_id=item["source_id"],
            source_uri=item.get("source_uri"),
            content_hash=digest,
            retrieved_at=_time(item["retrieved_at"]),
            observed_at=_time(item.get("observed_at")),
            valid_from=_time(item.get("valid_from")),
            valid_until=valid_until,
            jurisdiction=item.get("jurisdiction"),
            spatial_scope=item.get("spatial_scope"),
            measurement=content,
            unit=item.get("unit"),
            uncertainty=(
                Uncertainty(**item["uncertainty"]) if item.get("uncertainty") else None
            ),
            licence_status=item.get("licence_status", "RESEARCH_FIXTURE"),
            verification_status=status,
            provenance=Provenance(
                provenance_data.get("source_identifier") or item["source_id"],
                provenance_data.get("retrieval_mechanism", "UNDECLARED"),
                digest,
                tuple(provenance_data.get("transformation_ids", ())),
                tuple(provenance_data.get("upstream_evidence_ids", ())),
            ),
            metadata={
                **item.get("metadata", {}),
                "provenance_complete": provenance_complete,
            },
        )

    def convert_all(
        self, items: list[Mapping[str, Any]], *, evaluation_time: datetime
    ) -> tuple[EvidenceObject, ...]:
        return tuple(self.convert(x, evaluation_time=evaluation_time) for x in items)
