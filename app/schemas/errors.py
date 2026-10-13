from typing import Any

from pydantic import BaseModel, Field

from app.core.error_codes import OPENAPI_DOCUMENTED_ERROR_CODES


class ErrorDetail(BaseModel):
    code: str = Field(
        ...,
        description=(
            "Stable machine-readable key; branch on this value (not ``message``). "
            "Same set as ``docs/api/errors.md`` and ``app.core.error_codes.OPENAPI_DOCUMENTED_ERROR_CODES``."
        ),
        json_schema_extra={"enum": list(OPENAPI_DOCUMENTED_ERROR_CODES)},
    )
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


__all__ = ["ErrorDetail", "ErrorEnvelope"]
