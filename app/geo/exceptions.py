"""Geometry registry exceptions."""

from app.core.exceptions import GeoRiskApiError


class GeometryNotFoundError(GeoRiskApiError):
    """Raised when an asset geometry is not registered."""

    def __init__(self, asset_id: str) -> None:
        super().__init__(
            code="GEOMETRY_NOT_FOUND",
            message=f"No geometry registered for asset_id={asset_id!r}",
            status_code=404,
        )
        self.asset_id = asset_id


class GeometryAlreadyRegisteredError(GeoRiskApiError):
    """Raised when register() is called for an existing asset_id."""

    def __init__(self, asset_id: str) -> None:
        super().__init__(
            code="GEOMETRY_ALREADY_REGISTERED",
            message=f"Geometry already registered for asset_id={asset_id!r}",
            status_code=409,
        )
        self.asset_id = asset_id


class RasterSourceConfigError(Exception):
    """Raised when a CDS-backed raster source is requested without API credentials."""

    def __init__(self, source: str, detail: str = "COPERNICUS_CDS_API_KEY or CDSAPI_KEY not configured") -> None:
        self.source = source
        self.detail = detail
        super().__init__(f"{source}: {detail}")
