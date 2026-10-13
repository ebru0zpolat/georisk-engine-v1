"""Annex B.7 adaptation-outcome schema fields (collection/analytics come later)."""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class MeasureStatus(str, Enum):
    """Lifecycle of a recommended adaptation measure."""

    recommended = "recommended"
    accepted = "accepted"
    implemented = "implemented"
    declined = "declined"
    not_applicable = "not_applicable"
    unknown = "unknown"


class AdaptationOutcome(BaseModel):
    """Track recommended → implemented → reviewed outcomes (Annex B.7)."""

    measure_id: str | None = Field(default=None, description="Optional catalogue / measure identifier.")
    measure_status: MeasureStatus | None = Field(default=None)
    implemented_date: date | None = Field(
        default=None,
        description="Date the measure was implemented (customer-confirmed).",
    )
    post_implementation_review: str | None = Field(
        default=None,
        description="Free-text review of realised risk reduction / lessons learned.",
    )
    share_outcome_consented: bool = Field(
        default=False,
        description="Customer consented to share outcome data for aggregated analytics.",
    )
    anonymise_in_aggregate: bool = Field(
        default=True,
        description="When sharing is consented, strip identifiers in aggregate datasets.",
    )


__all__ = ["AdaptationOutcome", "MeasureStatus"]
