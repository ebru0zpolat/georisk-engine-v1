"""BAG PDOK OGC API v2 Connector.

Fetches real Amsterdam building data from the BAG (Basisregistratie
Adressen en Gebouwen) via PDOK's OGC API Features v2 endpoints.

Production base: https://api.pdok.nl/kadaster/bag/ogc/v2

Collections:
  /collections/pand/items           — building geometry, bouwjaar, gebruiksdoel
  /collections/verblijfsobject/items — occupancy unit, oppervlakte, pand relations
  /collections/adres/items          — address records

License: Public Domain Mark 1.0 (BAG data via LV-BAG)
Authority: Kadaster (LV-BAG) / PDOK

Architecture:
  Live fetch → raw response saved as snapshot → SHA-256 sealed →
  deterministic replay from snapshot in CI.

Fail-closed:
  - Network failure → raise (not synthetic fallback)
  - Empty results → raise (not empty placeholder)
  - Schema change → snapshot hash mismatch → fail-closed
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Production BAG OGC API v2 endpoints
# ---------------------------------------------------------------------------

BAG_BASE_URL = "https://api.pdok.nl/kadaster/bag/ogc/v2"
BAG_PAND_URL = f"{BAG_BASE_URL}/collections/pand/items"
BAG_VERBLIJDSDOBJECT_URL = f"{BAG_BASE_URL}/collections/verblijfsobject/items"
BAG_ADRES_URL = f"{BAG_BASE_URL}/collections/adres/items"

# Amsterdam bounding box (CRS84 / WGS84 lon,lat order)
# Covers central Amsterdam non-residential area
# west,south,east,north = 3.9°E,52.3°N → 5.1°E,52.4°N
AMSTERDAM_BBOX_CRS84 = "3.9,52.3,5.1,52.4"

# License
BAG_LICENSE_ID = "Public Domain Mark 1.0"
BAG_LICENSE_NAME = "BAG data — Public Domain"
BAG_LICENSE_URL = "https://www.pdok.nl/introductie/-/article/basisregistratie-adressen-en-gebouwen-bag-"
BAG_AUTHORITY = "Kadaster (LV-BAG) / PDOK"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BAGPand:
    """A BAG pand (building) record.

    Schema per PDOK BAG OGC API v2 /collections/pand/items:
      - identificatie: string (pand ID)
      - bouwjaar: integer (construction year)
      - gebruiksdoel: string (use function)
      - geometry: GeoJSON Polygon (building footprint)
      - verblijfsobject: list[{href: string}] (relation array)
    """
    identificatie: str
    bouwjaar: int
    gebruiksdoel: str  # e.g. "woonfunctie", "kantoorfunctie"
    geometry: dict  # GeoJSON polygon
    verblijfsobject_hrefs: tuple[str, ...] = ()  # relation hrefs
    bbox: list[float] | None = None

    def to_dict(self) -> dict:
        return {
            "identificatie": self.identificatie,
            "bouwjaar": self.bouwjaar,
            "gebruiksdoel": self.gebruiksdoel,
            "geometry": self.geometry,
            "verblijfsobject_hrefs": list(self.verblijfsobject_hrefs),
        }


@dataclass(frozen=True)
class BAGVerblijfsobject:
    """A BAG verblijfsobject (building unit / occupancy) record.

    Schema per PDOK BAG OGC API v2 /collections/verblijfsobject/items:
      - identificatie: string (verblijfsobject ID)
      - gebruiksdoel: string (use function)
      - oppervlakte: number (floor area m²)
      - geometry: GeoJSON Point (centroid)
      - pand: list[{href: string}] (relation array)
    """
    identificatie: str
    pand_hrefs: tuple[str, ...]  # relation hrefs (1 or more)
    oppervlakte: float  # m²
    gebruiksdoel: str
    geometry: dict  # GeoJSON point (centroid)

    def to_dict(self) -> dict:
        return {
            "identificatie": self.identificatie,
            "pand_hrefs": list(self.pand_hrefs),
            "oppervlakte": self.oppervlakte,
            "gebruiksdoel": self.gebruiksdoel,
            "geometry": self.geometry,
        }


# ---------------------------------------------------------------------------
# Raw fetch result (preserves original HTTP bytes)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RawFetchResult:
    """Result of a raw HTTP fetch — preserves original response bytes.

    The critical invariant: raw_bytes is the EXACT HTTP response body.
    artifact_sha256 fingerprints these exact bytes.
    """
    source_url: str
    raw_bytes: bytes
    content_type: str
    retrieved_at: str  # ISO 8601
    http_status: int

    @property
    def artifact_sha256(self) -> str:
        """SHA-256 of the exact HTTP response body bytes."""
        return hashlib.sha256(self.raw_bytes).hexdigest()

    @property
    def normalized_content_sha256(self) -> str:
        """SHA-256 of canonical (sorted-keys) JSON representation.

        This is the structural content hash — separate from artifact hash.
        """
        data = json.loads(self.raw_bytes)
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def validate(self) -> None:
        """Fail-closed validation of the raw fetch result."""
        if self.http_status != 200:
            raise RuntimeError(
                f"HTTP {self.http_status} for {self.source_url}"
            )
        if not self.raw_bytes:
            raise RuntimeError(
                f"Empty response body from {self.source_url}"
            )
        data = json.loads(self.raw_bytes)
        if not isinstance(data, dict):
            raise RuntimeError(
                f"Response is not a JSON object from {self.source_url}"
            )
        if data.get("type") != "FeatureCollection":
            raise RuntimeError(
                f"Response type is '{data.get("type")}' not 'FeatureCollection' "
                f"from {self.source_url}"
            )
        features = data.get("features")
        if not isinstance(features, list):
            raise RuntimeError(
                f"'features' is not a list from {self.source_url}"
            )
        if not features:
            raise RuntimeError(
                f"'features' is empty from {self.source_url}"
            )


# ---------------------------------------------------------------------------
# Raw fetch functions
# ---------------------------------------------------------------------------

def raw_fetch(
    url: str,
    bbox: str = AMSTERDAM_BBOX_CRS84,
    limit: int = 20,
) -> RawFetchResult:
    """Fetch raw bytes from a PDOK OGC API v2 items endpoint.

    Returns RawFetchResult preserving exact HTTP response bytes.
    Raises RuntimeError on network, HTTP, or schema failure.
    """
    import urllib.request
    import urllib.parse
    from datetime import datetime, timezone

    params = urllib.parse.urlencode({
        "bbox": bbox,
        "limit": limit,
    })
    full_url = f"{url}?{params}"

    try:
        req = urllib.request.Request(
            full_url,
            headers={"Accept": "application/geo+json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            content_type = resp.headers.get("Content-Type", "application/geo+json")
            http_status = resp.status
    except Exception as e:
        raise RuntimeError(
            f"BAG fetch failed from {full_url}: {e}"
        ) from e

    result = RawFetchResult(
        source_url=full_url,
        raw_bytes=raw,
        content_type=content_type,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        http_status=http_status,
    )
    result.validate()
    return result


# ---------------------------------------------------------------------------
# Legacy fetch (returns parsed dict, for backward compat)
# ---------------------------------------------------------------------------

def fetch_bag_pands(
    bbox: str = AMSTERDAM_BBOX_CRS84,
    limit: int = 20,
) -> dict:
    """Fetch BAG pand records — returns parsed dict.

    Prefer raw_fetch() for new code that needs raw bytes.
    """
    result = raw_fetch(BAG_PAND_URL, bbox=bbox, limit=limit)
    return json.loads(result.raw_bytes)


def fetch_bag_verblijfsobjecten(
    bbox: str = AMSTERDAM_BBOX_CRS84,
    limit: int = 20,
) -> dict:
    """Fetch BAG verblijfsobject records — returns parsed dict.

    Prefer raw_fetch() for new code that needs raw bytes.
    """
    result = raw_fetch(BAG_VERBLIJDSDOBJECT_URL, bbox=bbox, limit=limit)
    return json.loads(result.raw_bytes)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _extract_pand_hrefs(props: dict) -> tuple[str, ...]:
    """Extract pand relation hrefs from verblijfsobject properties.

    PDOK BAG OGC API v2 exposes the relation as a 'pand.href' property
    containing a list of pand feature URLs.

    Actual PDOK payload shape:
      "pand.href": ["https://...pand/items/<uuid>"]
      or absent / null

    NOTE: href UUIDs are NOT BAG identificatie values.
    BAG identificatie must be resolved by following the feature reference.

    Returns a tuple of pand relation href strings.
    """
    pand_hrefs = props.get("pand.href")
    if not pand_hrefs or not isinstance(pand_hrefs, list):
        return ()

    return tuple(str(h) for h in pand_hrefs if h)


def _extract_vbo_hrefs(props: dict) -> tuple[str, ...]:
    """Extract verblijfsobject relation hrefs from pand properties.

    PDOK BAG OGC API v2 exposes the relation as a 'verblijfsobject.href'
    property containing a list of verblijfsobject feature URLs.

    Actual PDOK payload shape:
      "verblijfsobject.href": ["https://...verblijfsobject/items/<uuid>"]
      or null / absent

    NOTE: href UUIDs are NOT BAG identificatie values.
    BAG identificatie must be resolved by following the feature reference.

    Returns a tuple of verblijfsobject relation href strings.
    """
    vbo_hrefs = props.get("verblijfsobject.href")
    if not vbo_hrefs or not isinstance(vbo_hrefs, list):
        return ()

    return tuple(str(h) for h in vbo_hrefs if h)


def parse_bag_pand(feature: dict) -> BAGPand:
    """Parse a BAG pand GeoJSON feature into a BAGPand record.

    Expected schema (PDOK BAG OGC API v2):
      properties.identificatie: string
      properties.bouwjaar: integer
      properties.gebruiksdoel: string
      geometry: GeoJSON Polygon
      properties.verblijfsobject: list[{href: string}] (optional relation array)
    """
    props = feature.get("properties", {})
    geom = feature.get("geometry", {})

    identificatie = str(props.get("identificatie", ""))
    bouwjaar = int(props.get("bouwjaar", 0))
    gebruiksdoel = str(props.get("gebruiksdoel", ""))
    vbo_hrefs = _extract_vbo_hrefs(props)

    return BAGPand(
        identificatie=identificatie,
        bouwjaar=bouwjaar,
        gebruiksdoel=gebruiksdoel,
        geometry=geom,
        verblijfsobject_hrefs=vbo_hrefs,
    )


def parse_bag_verblijfsobject(feature: dict) -> BAGVerblijfsobject:
    """Parse a BAG verblijfsobject GeoJSON feature.

    Expected schema (PDOK BAG OGC API v2):
      properties.identificatie: string
      properties.gebruiksdoel: string
      properties.oppervlakte: number
      geometry: GeoJSON Point
      properties.pand: list[{href: string}] (relation array)
    """
    props = feature.get("properties", {})
    geom = feature.get("geometry", {})

    identificatie = str(props.get("identificatie", ""))
    pand_hrefs = _extract_pand_hrefs(props)
    oppervlakte = float(props.get("oppervlakte", 0))
    gebruiksdoel = str(props.get("gebruiksdoel", ""))

    return BAGVerblijfsobject(
        identificatie=identificatie,
        pand_hrefs=pand_hrefs,
        oppervlakte=oppervlakte,
        gebruiksdoel=gebruiksdoel,
        geometry=geom,
    )


# ---------------------------------------------------------------------------
# Snapshot utilities
# ---------------------------------------------------------------------------

def save_raw_snapshot(
    result: RawFetchResult,
    snapshot_path: Path,
) -> dict:
    """Save exact HTTP response bytes as a snapshot.

    Returns provenance metadata dict.
    Does NOT normalize or re-serialize the bytes.
    """
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_bytes(result.raw_bytes)

    return {
        "source_url": result.source_url,
        "artifact_sha256": result.artifact_sha256,
        "normalized_content_sha256": result.normalized_content_sha256,
        "retrieved_at": result.retrieved_at,
        "http_status": result.http_status,
        "content_type": result.content_type,
        "byte_length": len(result.raw_bytes),
        "snapshot_path": str(snapshot_path),
    }


def save_snapshot(
    data: dict,
    snapshot_path: Path,
) -> str:
    """Save parsed dict as a deterministic JSON snapshot.

    Returns the SHA-256 of the saved bytes.
    NOTE: This is the normalized-content hash, not the artifact hash.
    """
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)

    # Deterministic JSON: sorted keys, no extra whitespace
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    raw_bytes = canonical.encode("utf-8")

    snapshot_path.write_bytes(raw_bytes)
    return hashlib.sha256(raw_bytes).hexdigest()
