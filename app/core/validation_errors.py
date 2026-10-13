"""Map Pydantic / FastAPI validation errors to stable GeoRisk error codes."""

from __future__ import annotations

from typing import Any


def validation_error_parts(errors: list[Any]) -> tuple[str, str, dict[str, Any]]:
    """Return ``(code, message, details)`` for ``RequestValidationError.errors()``."""
    empty: dict[str, Any] = {}

    if not errors:
        return "VALIDATION_ERROR", "Request validation failed.", empty

    def loc_str(err: Any) -> str:
        loc = err.get("loc") or ()
        return ".".join(str(x) for x in loc)

    for err in errors:
        loc_s = loc_str(err)
        typ = str(err.get("type", ""))
        msg = str(err.get("msg", "Validation failed"))

        if typ in {
            "greater_than_equal",
            "less_than_equal",
            "greater_than",
            "less_than",
        }:
            if any(
                k in loc_s
                for k in (
                    "latitude",
                    "longitude",
                    ".lat",
                    ".lon",
                    "query.lat",
                    "query.lon",
                )
            ):
                return (
                    "INVALID_COORDINATES",
                    "Latitude or longitude is outside WGS84 bounds.",
                    empty,
                )

        if typ == "missing":
            if "assets" in loc_s and loc_s.endswith(".id"):
                return "INVALID_ASSET", "Each batch asset must include a non-empty id.", empty
            if "assets" in loc_s and (
                ".lat" in loc_s or ".lon" in loc_s or loc_s.endswith("lat") or loc_s.endswith("lon")
            ):
                return "INVALID_ASSET", "Each batch asset must include lat and lon.", empty

        if "preset_id" in loc_s and typ == "missing":
            return "PRESET_NOT_FOUND", "preset_id is required for this request.", empty

        if "preset_id" in loc_s:
            return "PRESET_NOT_FOUND", msg, empty

        if typ == "value_error" and "Unknown preset_id" in msg:
            return "PRESET_NOT_FOUND", "Unknown preset_id; see REGISTERED_PRESET_IDS.", empty

        if "assets" in loc_s and typ in ("too_short", "list_type"):
            return "INVALID_BATCH", "The assets list must contain at least one row.", empty

        if "assets" in loc_s and typ == "too_long":
            return "BATCH_TOO_LARGE", "Too many assets in one batch request.", empty

        if typ == "string_too_short" and "assets" in loc_s and ".id" in loc_s:
            return "INVALID_ASSET", "Each batch asset must include a non-empty id.", empty

    first = errors[0]
    return "VALIDATION_ERROR", str(first.get("msg", "Validation failed.")), empty


def code_and_message_for_validation_errors(errors: list[Any]) -> tuple[str, str]:
    code, message, _ = validation_error_parts(errors)
    return code, message


__all__ = ["code_and_message_for_validation_errors", "validation_error_parts"]
