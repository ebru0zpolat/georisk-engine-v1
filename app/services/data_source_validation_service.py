from __future__ import annotations

from app.core.data_source_registry import get_data_source, list_data_sources
from app.core.data_source_validation import validate_all_sources, validate_source
from app.schemas.data_sources import (
    DataSourceValidationReport,
    SourceValidationOut,
    ValidationCheckOut,
)


def build_validation_report() -> DataSourceValidationReport:
    results = validate_all_sources()
    sources = [
        SourceValidationOut(
            source_id=r.source_id,
            delivery_mode=r.delivery_mode,
            passed=r.passed,
            checks=[
                ValidationCheckOut(
                    id=c.id,
                    description=c.description,
                    criterion=c.criterion,
                    status=c.status,
                    detail=c.detail,
                )
                for c in r.checks
            ],
        )
        for r in results
    ]
    passed_count = sum(1 for s in sources if s.passed)
    return DataSourceValidationReport(
        source_count=len(sources),
        passed_count=passed_count,
        sources=sources,
    )


def build_source_validation(source_id: str) -> SourceValidationOut | None:
    entry = get_data_source(source_id)
    if entry is None:
        return None
    result = validate_source(entry)
    return SourceValidationOut(
        source_id=result.source_id,
        delivery_mode=result.delivery_mode,
        passed=result.passed,
        checks=[
            ValidationCheckOut(
                id=c.id,
                description=c.description,
                criterion=c.criterion,
                status=c.status,
                detail=c.detail,
            )
            for c in result.checks
        ],
    )
