"""Blueprint-aligned risk grid tiles (Sprint 5 / GEO-58 pilot).

Generates PNG tiles for a fixed Marmara pilot bbox using a deterministic
normalized risk field (not live CDS). Contract matches blueprint:
``GET /v1/tiles/{layer}/{z}/{x}/{y}.png``.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass

from PIL import Image

# Marmara / NW Turkey pilot (WGS84)
PILOT_WEST = 26.0
PILOT_SOUTH = 39.5
PILOT_EAST = 30.5
PILOT_NORTH = 42.0
TILE_SIZE = 256
SUPPORTED_LAYERS = frozenset({"total_risk", "climate", "water"})


@dataclass(frozen=True)
class TileNotInPilot(Exception):
    """Raised when the XYZ tile does not intersect the pilot bbox."""

    message: str = "Tile outside pilot bbox"


def _lon_lat_to_pixel(lon: float, lat: float, z: int) -> tuple[float, float]:
    """Web Mercator world pixel coords at zoom z (continuous)."""
    n = 2.0**z
    x = (lon + 180.0) / 360.0 * n * TILE_SIZE
    lat_r = math.radians(lat)
    y = (1.0 - math.log(math.tan(lat_r) + 1.0 / math.cos(lat_r)) / math.pi) / 2.0 * n * TILE_SIZE
    return x, y


def tile_bounds_lonlat(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """Return (west, south, east, north) for XYZ tile."""
    n = 2.0**z
    west = x / n * 360.0 - 180.0
    east = (x + 1) / n * 360.0 - 180.0

    def y_to_lat(ty: float) -> float:
        return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * ty / n))))

    north = y_to_lat(y)
    south = y_to_lat(y + 1)
    return west, south, east, north


def _intersects_pilot(west: float, south: float, east: float, north: float) -> bool:
    return not (east < PILOT_WEST or west > PILOT_EAST or north < PILOT_SOUTH or south > PILOT_NORTH)


def _risk_at(lon: float, lat: float, layer: str) -> float:
    """Deterministic 0–1 risk field for the pilot (blueprint-style normalize)."""
    # Coastal / Marmara bias + gentle gradients
    coastal = max(0.0, 1.0 - abs(lat - 40.8) / 2.5)
    east_west = (lon - PILOT_WEST) / (PILOT_EAST - PILOT_WEST)
    climate = min(1.0, max(0.0, 0.35 * coastal + 0.4 * east_west + 0.15))
    water = min(1.0, max(0.0, 0.55 * coastal + 0.2 * (1.0 - east_west)))
    total = min(1.0, max(0.0, climate * 0.6 + water * 0.4))
    if layer == "climate":
        return climate
    if layer == "water":
        return water
    return total


def _color(risk: float) -> tuple[int, int, int, int]:
    """Green → yellow → red ramp."""
    r = int(min(255, max(0, risk * 255)))
    g = int(min(255, max(0, (1.0 - risk) * 200)))
    b = 40
    return (r, g, b, 220)


def render_tile_png(layer: str, z: int, x: int, y: int) -> bytes:
    if layer not in SUPPORTED_LAYERS:
        raise ValueError(f"Unsupported layer: {layer}")
    if z < 0 or z > 12:
        raise ValueError("Zoom must be in 0..12 for pilot tiles")
    west, south, east, north = tile_bounds_lonlat(z, x, y)
    if not _intersects_pilot(west, south, east, north):
        # Transparent empty tile (map clients expect 200 PNG)
        img = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    img = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
    px = img.load()
    assert px is not None
    for row in range(TILE_SIZE):
        for col in range(TILE_SIZE):
            # Sample lon/lat at pixel center
            lon = west + (col + 0.5) / TILE_SIZE * (east - west)
            lat = north - (row + 0.5) / TILE_SIZE * (north - south)
            if lon < PILOT_WEST or lon > PILOT_EAST or lat < PILOT_SOUTH or lat > PILOT_NORTH:
                continue
            risk = _risk_at(lon, lat, layer)
            px[col, row] = _color(risk)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


__all__ = [
    "PILOT_EAST",
    "PILOT_NORTH",
    "PILOT_SOUTH",
    "PILOT_WEST",
    "SUPPORTED_LAYERS",
    "render_tile_png",
    "tile_bounds_lonlat",
]
