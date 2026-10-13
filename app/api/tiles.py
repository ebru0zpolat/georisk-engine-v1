"""Blueprint tile endpoint — ``GET /v1/tiles/{layer}/{z}/{x}/{y}.png``."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.services.risk_tiles import SUPPORTED_LAYERS, render_tile_png

router = APIRouter()


@router.get("/tiles/{layer}/{z}/{x}/{y}.png")
def get_risk_tile(layer: str, z: int, x: int, y: int) -> Response:
    if layer not in SUPPORTED_LAYERS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown layer '{layer}'. Supported: {sorted(SUPPORTED_LAYERS)}",
        )
    try:
        png = render_tile_png(layer, z, x, y)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(
        content=png,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-GeoRisk-Tile-Layer": layer,
            "X-GeoRisk-Tile-Pilot": "marmara-v1",
        },
    )
