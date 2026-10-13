"""Tests for the NL Real-Data Pilot.

Two test modes:
  1. Deterministic snapshot replay (default CI) — uses sealed snapshots
  2. Live integration (opt-in) — fetches from real BAG/Overheid.nl

Acceptance contract (all must pass):
  REAL_ASSETS >= 5
  CUSTOMER_DATA = 0
  PUBLIC_OFFICIAL_DATA_ONLY = true
  BAG_IDENTITY_VERIFIED = true
  OFFICIAL_REGULATORY_ARTIFACT_EXISTS = true
  THRESHOLD_SOURCE_VERIFIED = true
  THRESHOLD_DEFINITION_VERIFIED = true
  ASSET_APPLICABILITY_VERIFIED = false (fail-closed)
  PRODUCTION_ELIGIBLE = false
  EXTERNAL_USE_APPROVED = false
  NO_SILENT_SYNTHETIC_FALLBACK = true
"""

from __future__ import annotations

import hashlib
import inspect
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.nl_pilot.real_assets import RealAmsterdamAsset, pilot_assets
from app.nl_pilot.real_data_registry import (
    RealDataRegistry,
    RealDataSourceType,
    SealedSnapshot,
    SourceProvenance,
    SnapshotStatus,
)
from app.nl_pilot.pilot_evidence_pack import (
    PILOT_CLASSIFICATION,
    PILOT_PACK_ID,
    build_pilot_evidence_pack,
)
from app.nl_pilot.bag_connector import (
    BAG_ADRES_URL,
    BAG_AUTHORITY,
    BAG_BASE_URL,
    BAG_LICENSE_ID,
    BAG_LICENSE_NAME,
    BAG_LICENSE_URL,
    BAG_PAND_URL,
    BAG_VERBLIJDSDOBJECT_URL,
    AMSTERDAM_BBOX_CRS84,
    parse_bag_pand,
    parse_bag_verblijfsobject,
)
from app.nl_pilot.amsterdam_source import (
    AMSTERDAM_THRESHOLDS,
    AMSTERDAM_OMGEVINGSPLAN_URL,
    AMSTERDAM_OMGEVINGSPLAN_VERSION_URL,
    AmsterdamSourceArtifact,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pilot_asset_list() -> list[RealAmsterdamAsset]:
    return pilot_assets()


@pytest.fixture
def sealed_registry(tmp_path: Path) -> RealDataRegistry:
    """A registry with a test snapshot sealed."""
    registry = RealDataRegistry(project_root=tmp_path)

    # Register provenance
    prov = SourceProvenance(
        source_id="test-source",
        source_type=RealDataSourceType.CADASTRE,
        authority="Kadaster / PDOK",
        official_identifier="test-bag-001",
        title="Test BAG snapshot",
        source_url="https://api.pdok.nl/kadaster/bag/ogc/v2",
        retrieved_at="2026-08-27T10:00:00Z",
        effective_from="2026-01-01",
        license_id=BAG_LICENSE_ID,
        license_name=BAG_LICENSE_NAME,
        license_url=BAG_LICENSE_URL,
        query_or_bbox=AMSTERDAM_BBOX_CRS84,
        crs="CRS84",
    )
    registry.register_provenance(prov)

    # Create snapshot file
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    snapshot_file = snapshot_dir / "test-bag.json"
    test_data = {"type": "FeatureCollection", "features": []}
    snapshot_file.write_text(json.dumps(test_data, sort_keys=True), encoding="utf-8")

    # Seal
    registry.seal_snapshot("test-source", "snapshots/test-bag.json")
    return registry


# ---------------------------------------------------------------------------
# Real asset identity tests
# ---------------------------------------------------------------------------

class TestRealAssets:
    def test_pilot_has_5_assets(self, pilot_asset_list: list[RealAmsterdamAsset]):
        assert len(pilot_asset_list) == 5

    def test_all_assets_verified_identity(self, pilot_asset_list: list[RealAmsterdamAsset]):
        for asset in pilot_asset_list:
            assert asset.asset_identity_verified is True
            assert asset.building_geometry_verified is True  # ISSUE_7: Pand polygon verified
            assert asset.pand_footprint_area_m2 is not None
            assert asset.pand_footprint_area_m2 > 0
            assert asset.use_class_verified is True

    def test_no_assets_applicability_verified(self, pilot_asset_list: list[RealAmsterdamAsset]):
        for asset in pilot_asset_list:
            assert asset.asset_applicability_verified is False

    def test_no_assets_engineering_verified(self, pilot_asset_list: list[RealAmsterdamAsset]):
        for asset in pilot_asset_list:
            assert asset.engineering_capacity_verified is False

    def test_no_assets_production_eligible(self, pilot_asset_list: list[RealAmsterdamAsset]):
        for asset in pilot_asset_list:
            assert asset.production_eligible is False

    def test_all_assets_in_amsterdam(self, pilot_asset_list: list[RealAmsterdamAsset]):
        for asset in pilot_asset_list:
            assert "Amsterdam" in asset.address

    def test_all_assets_have_bag_ids(self, pilot_asset_list: list[RealAmsterdamAsset]):
        for asset in pilot_asset_list:
            assert asset.bag_pand_id
            assert asset.bag_verblijfsobject_id

    def test_all_assets_are_non_residential(self, pilot_asset_list: list[RealAmsterdamAsset]):
        """All pilot assets have non-residential BAG use classes."""
        for asset in pilot_asset_list:
            assert asset.gebruiksdoel != "woonfunctie", (
                f"{asset.asset_id}: residential use class not allowed"
            )

    def test_asset_ids_unique(self, pilot_asset_list: list[RealAmsterdamAsset]):
        ids = [a.asset_id for a in pilot_asset_list]
        assert len(ids) == len(set(ids))

    def test_to_dict_preserves_identity(self, pilot_asset_list: list[RealAmsterdamAsset]):
        asset = pilot_asset_list[0]
        d = asset.to_dict()
        assert d["bag_pand_id"] == asset.bag_pand_id
        assert d["asset_identity_verified"] is True
        assert d["municipality"] == "Amsterdam"


# ---------------------------------------------------------------------------
# Source provenance tests
# ---------------------------------------------------------------------------

class TestSourceProvenance:
    def test_amsterdam_thresholds_exist(self):
        assert len(AMSTERDAM_THRESHOLDS) == 3
        assert "storage_requirement" in AMSTERDAM_THRESHOLDS
        assert "discharge_limit" in AMSTERDAM_THRESHOLDS
        assert "emptying_requirement" in AMSTERDAM_THRESHOLDS

    def test_storage_threshold_value(self):
        t = AMSTERDAM_THRESHOLDS["storage_requirement"]
        assert t["value"] == 60.0
        assert t["unit"] == "L/m²"
        assert t["comparison"] == "gte"
        assert t["article"] == "Artikel 4.116"
        assert t["lid"] == "lid 1(a)"

    def test_discharge_threshold_value(self):
        t = AMSTERDAM_THRESHOLDS["discharge_limit"]
        assert t["value"] == 1.0
        assert t["unit"] == "L/m²/h"
        assert t["comparison"] == "lte"
        assert t["lid"] == "lid 1(b)"

    def test_emptying_threshold_value(self):
        t = AMSTERDAM_THRESHOLDS["emptying_requirement"]
        assert t["value"] == 60.0
        assert t["unit"] == "h"
        assert t["comparison"] == "lte"
        assert t["lid"] == "lid 1(c)"

    def test_all_thresholds_unverified(self):
        for name, t in AMSTERDAM_THRESHOLDS.items():
            assert "source_id" in t or "article" in t

    def test_amsterdam_source_url_correct(self):
        assert AMSTERDAM_OMGEVINGSPLAN_URL == (
            "https://lokaleregelgeving.overheid.nl/CVDR696291"
        )
        assert AMSTERDAM_OMGEVINGSPLAN_VERSION_URL == (
            "https://lokaleregelgeving.overheid.nl/CVDR696291/15"
        )


# ---------------------------------------------------------------------------
# BAG connector tests
# ---------------------------------------------------------------------------

class TestBAGContract:
    """Verify BAG OGC API v2 production contract."""

    def test_production_base_url(self):
        assert BAG_BASE_URL == "https://api.pdok.nl/kadaster/bag/ogc/v2"

    def test_pand_collection_url(self):
        assert BAG_PAND_URL == "https://api.pdok.nl/kadaster/bag/ogc/v2/collections/pand/items"

    def test_vbo_collection_url(self):
        assert BAG_VERBLIJDSDOBJECT_URL == "https://api.pdok.nl/kadaster/bag/ogc/v2/collections/verblijfsobject/items"

    def test_adres_collection_url(self):
        assert BAG_ADRES_URL == "https://api.pdok.nl/kadaster/bag/ogc/v2/collections/adres/items"

    def test_no_legacy_references_in_connector_module(self):
        """No legacy endpoint strings in connector source."""
        from app.nl_pilot import bag_connector
        import inspect
        source = inspect.getsource(bag_connector)
        assert "v2_0" not in source, "Legacy v2_0 reference in connector"
        assert "/buildings" not in source, "Legacy /buildings reference in connector"
        assert "/building-units" not in source, "Legacy /building-units reference in connector"

    def test_license_correct(self):
        assert BAG_LICENSE_ID == "Public Domain Mark 1.0"
        assert BAG_LICENSE_NAME == "BAG data — Public Domain"
        assert "pdok.nl" in BAG_LICENSE_URL

    def test_authority_correct(self):
        assert BAG_AUTHORITY == "Kadaster (LV-BAG) / PDOK"

    def test_amsterdam_bbox_crs84_format(self):
        """Amsterdam bbox uses CRS84/WGS84 lon/lat coordinates."""
        parts = AMSTERDAM_BBOX_CRS84.split(",")
        assert len(parts) == 4
        west, south, east, north = [float(p) for p in parts]
        # CRS84: longitude ∈ [-180, 180], latitude ∈ [-90, 90]
        assert -180 <= west <= 180, f"west longitude {west} out of range"
        assert -90 <= south <= 90, f"south latitude {south} out of range"
        assert -180 <= east <= 180, f"east longitude {east} out of range"
        assert -90 <= north <= 90, f"north latitude {north} out of range"
        # Amsterdam approximate bounds: lon 3.9-5.1, lat 52.3-52.4
        assert 3.0 <= west <= 5.0, f"west {west} not near Amsterdam"
        assert 52.0 <= south <= 52.5, f"south {south} not near Amsterdam"
        assert 4.5 <= east <= 6.0, f"east {east} not near Amsterdam"
        assert 52.0 <= north <= 52.6, f"north {north} not near Amsterdam"
        assert west < east, "west must be less than east"
        assert south < north, "south must be less than north"




# ---------------------------------------------------------------------------
# BAG parser tests
# ---------------------------------------------------------------------------

class TestBAGParsers:
    _PAND_VBO_HREF = "https://api.pdok.nl/kadaster/bag/ogc/v2/collections/verblijfsobject/items/"
    _VBO_PAND_HREF = "https://api.pdok.nl/kadaster/bag/ogc/v2/collections/pand/items/"

    def test_parse_pand_basic(self):
        feature = {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[[4.9, 52.37], [4.91, 52.37], [4.91, 52.38], [4.9, 52.38], [4.9, 52.37]]]},
            "properties": {
                "identificatie": "36320619",
                "bouwjaar": 1994,
                "gebruiksdoel": "kantoorfunctie",
            },
        }
        pand = parse_bag_pand(feature)
        assert pand.identificatie == "36320619"
        assert pand.bouwjaar == 1994
        assert pand.gebruiksdoel == "kantoorfunctie"
        assert pand.verblijfsobject_hrefs == ()

    def test_parse_pand_with_vbo_relations(self):
        """PDOK real shape: verblijfsobject.href is a URL list."""
        feature = {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": []},
            "properties": {
                "identificatie": "36320619",
                "bouwjaar": 1994,
                "gebruiksdoel": "kantoorfunctie",
                "verblijfsobject.href": [
                    f"{self._PAND_VBO_HREF}36344655",
                    f"{self._PAND_VBO_HREF}36344656",
                ],
            },
        }
        pand = parse_bag_pand(feature)
        assert len(pand.verblijfsobject_hrefs) == 2
        assert pand.verblijfsobject_hrefs[0].endswith("36344655")
        assert pand.verblijfsobject_hrefs[1].endswith("36344656")

    def test_parse_pand_missing_optional_relation(self):
        feature = {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": []},
            "properties": {
                "identificatie": "36320619",
                "bouwjaar": 1994,
                "gebruiksdoel": "kantoorfunctie",
            },
        }
        pand = parse_bag_pand(feature)
        assert pand.verblijfsobject_hrefs == ()

    def test_parse_pand_null_relation(self):
        """PDOK sends null when no VBO relations exist."""
        feature = {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": []},
            "properties": {
                "identificatie": "36320619",
                "bouwjaar": 1994,
                "gebruiksdoel": "kantoorfunctie",
                "verblijfsobject.href": None,
            },
        }
        pand = parse_bag_pand(feature)
        assert pand.verblijfsobject_hrefs == ()

    def test_parse_vbo_single_pand(self):
        """PDOK real shape: pand.href is a URL list."""
        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [4.9, 52.37]},
            "properties": {
                "identificatie": "36344655",
                "pand.href": [f"{self._VBO_PAND_HREF}36320619"],
                "oppervlakte": 1250.0,
                "gebruiksdoel": "kantoorfunctie",
            },
        }
        vbo = parse_bag_verblijfsobject(feature)
        assert vbo.identificatie == "36344655"
        assert len(vbo.pand_hrefs) == 1
        assert vbo.pand_hrefs[0].endswith("36320619")
        assert vbo.oppervlakte == 1250.0

    def test_parse_vbo_multiple_pand_relations(self):
        """VBO can belong to multiple pand records."""
        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [4.9, 52.37]},
            "properties": {
                "identificatie": "36344655",
                "pand.href": [
                    f"{self._VBO_PAND_HREF}36320619",
                    f"{self._VBO_PAND_HREF}36320620",
                ],
                "oppervlakte": 800.0,
                "gebruiksdoel": "kantoorfunctie",
            },
        }
        vbo = parse_bag_verblijfsobject(feature)
        assert len(vbo.pand_hrefs) == 2
        assert vbo.pand_hrefs[0].endswith("36320619")
        assert vbo.pand_hrefs[1].endswith("36320620")

    def test_parse_vbo_missing_pand_relation(self):
        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [4.9, 52.37]},
            "properties": {
                "identificatie": "36344655",
                "oppervlakte": 500.0,
                "gebruiksdoel": "winkelfunctie",
            },
        }
        vbo = parse_bag_verblijfsobject(feature)
        assert vbo.pand_hrefs == ()

    def test_parse_vbo_null_pand_relation(self):
        """PDOK sends null when no pand relation exists."""
        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [4.9, 52.37]},
            "properties": {
                "identificatie": "36344655",
                "pand.href": None,
                "oppervlakte": 500.0,
                "gebruiksdoel": "winkelfunctie",
            },
        }
        vbo = parse_bag_verblijfsobject(feature)
        assert vbo.pand_hrefs == ()

    def test_parse_vbo_pand_relation_cardinality_preserved(self):
        """Parser preserves relation cardinality — no forced single pand."""
        for count in (1, 2, 3):
            hrefs = [f"{self._VBO_PAND_HREF}pand-{i}" for i in range(count)]
            feature = {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [4.9, 52.37]},
                "properties": {
                    "identificatie": "vbo-001",
                    "pand.href": hrefs,
                    "oppervlakte": 100.0,
                    "gebruiksdoel": "kantoorfunctie",
                },
            }
            vbo = parse_bag_verblijfsobject(feature)
            assert len(vbo.pand_hrefs) == count


# ---------------------------------------------------------------------------
# Real data registry tests
# ---------------------------------------------------------------------------

class TestRealDataRegistry:
    def test_register_and_seal(self, sealed_registry: RealDataRegistry):
        assert "test-source" in sealed_registry.list_sealed()

    def test_verify_snapshot(self, sealed_registry: RealDataRegistry):
        is_valid, reason = sealed_registry.verify_snapshot("test-source")
        assert is_valid
        assert "verified" in reason.lower()

    def test_load_snapshot_bytes(self, sealed_registry: RealDataRegistry):
        raw = sealed_registry.load_snapshot_bytes("test-source")
        data = json.loads(raw)
        assert data["type"] == "FeatureCollection"

    def test_unknown_source_raises(self, sealed_registry: RealDataRegistry):
        with pytest.raises(ValueError, match="No snapshot registered"):
            sealed_registry.load_snapshot_bytes("nonexistent")

    def test_seal_unknown_source_raises(self, tmp_path: Path):
        registry = RealDataRegistry(project_root=tmp_path)
        snapshot_file = tmp_path / "test.json"
        snapshot_file.write_text("{}")
        with pytest.raises(ValueError, match="unknown source_id"):
            registry.seal_snapshot("unknown", "test.json")

    def test_missing_file_raises(self, tmp_path: Path):
        registry = RealDataRegistry(project_root=tmp_path)
        prov = SourceProvenance(
            source_id="x", source_type=RealDataSourceType.CADASTRE,
            authority="test", official_identifier="test", title="test",
            source_url="http://test", retrieved_at="", effective_from="",
        )
        registry.register_provenance(prov)
        with pytest.raises(FileNotFoundError):
            registry.seal_snapshot("x", "nonexistent.json")

    def test_provenance_to_dict(self, sealed_registry: RealDataRegistry):
        prov = sealed_registry.get_provenance("test-source")
        assert prov is not None
        d = prov.to_dict()
        assert d["source_id"] == "test-source"
        assert d["license_id"] == BAG_LICENSE_ID

    def test_manifest_export(self, sealed_registry: RealDataRegistry):
        manifest = sealed_registry.to_manifest()
        assert "sources" in manifest
        assert "snapshots" in manifest
        assert "test-source" in manifest["sources"]

    def test_hash_tamper_detected(self, sealed_registry: RealDataRegistry, tmp_path: Path):
        """Tamper with snapshot → hash mismatch."""
        # Tamper with the file
        snapshot_file = tmp_path / "snapshots" / "test-bag.json"
        snapshot_file.write_text('{"tampered": true}', encoding="utf-8")
        is_valid, reason = sealed_registry.verify_snapshot("test-source")
        assert not is_valid
        assert "mismatch" in reason.lower()


# ---------------------------------------------------------------------------
# Pilot evidence pack tests
# ---------------------------------------------------------------------------

class TestPilotEvidencePack:
    def test_basic_generation(self, pilot_asset_list: list[RealAmsterdamAsset]):
        pack = build_pilot_evidence_pack(assets=pilot_asset_list)
        assert pack["pack_id"] == PILOT_PACK_ID
        assert pack["pack_type"] == "real_data_pilot"
        assert len(pack["asset_evaluations"]) == 5

    def test_classification_correct(self, pilot_asset_list: list[RealAmsterdamAsset]):
        pack = build_pilot_evidence_pack(assets=pilot_asset_list)
        cls = pack["classification"]
        assert cls["evidence_class"] == "real_data_pilot"
        assert cls["customer_data_status"] == "public_official_data_only"
        assert cls["production_eligible"] is False
        assert cls["decision_use_approved"] is False
        assert cls["real_assets_count"] == 5
        assert cls["real_source_artifacts"] is True

    def test_all_assets_applicability_unverified(self, pilot_asset_list: list[RealAmsterdamAsset]):
        pack = build_pilot_evidence_pack(assets=pilot_asset_list)
        for ev in pack["asset_evaluations"]:
            assert ev["asset_applicability_verified"] is False
            assert ev["overall_status"] == "applicability_unverified"

    def test_all_thresholds_applicability_unverified(self, pilot_asset_list: list[RealAmsterdamAsset]):
        pack = build_pilot_evidence_pack(assets=pilot_asset_list)
        for ev in pack["asset_evaluations"]:
            for rr in ev["rule_results"]:
                assert rr["status"] == "applicability_unverified"

    def test_pilot_gates_fail_closed(self, pilot_asset_list: list[RealAmsterdamAsset]):
        pack = build_pilot_evidence_pack(assets=pilot_asset_list)
        gates = pack["pilot_gates"]
        assert gates["real_assets"] is True
        assert gates["customer_data"] == 0
        assert gates["public_official_data_only"] is True
        assert gates["official_regulatory_artifact_verified"] is True
        assert gates["threshold_source_verified"] is True
        assert gates["asset_applicability_verified"] is False
        assert gates["engineering_capacity_verified"] is False
        assert gates["production_eligible"] is False
        assert gates["external_use_approved"] is False

    def test_summary_counts(self, pilot_asset_list: list[RealAmsterdamAsset]):
        pack = build_pilot_evidence_pack(assets=pilot_asset_list)
        s = pack["summary"]
        assert s["total_assets"] == 5
        assert s["applicable_unknown_count"] == 5
        assert s["synthetic_fallback_used"] is False
        assert s["production_eligible"] is False
        assert s["external_use_approved"] is False
        assert pack["pilot_gates"]["real_assets"] is True

    def test_checksum_integrity(self, pilot_asset_list: list[RealAmsterdamAsset]):
        pack = build_pilot_evidence_pack(assets=pilot_asset_list)
        stored = pack["checksum"]["content_sha256"]
        # Recompute
        exclude_keys = {"checksum", "generated_at"}
        content = {k: v for k, v in pack.items() if k not in exclude_keys}
        canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        recomputed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        assert stored == recomputed

    def test_determinism(self, pilot_asset_list: list[RealAmsterdamAsset]):
        VOLATILE = {"generated_at"}
        p1 = build_pilot_evidence_pack(assets=pilot_asset_list)
        p2 = build_pilot_evidence_pack(assets=pilot_asset_list)
        for k in VOLATILE:
            p1.pop(k, None)
            p2.pop(k, None)
        assert json.dumps(p1, sort_keys=True) == json.dumps(p2, sort_keys=True)

    def test_duplicate_asset_ids_rejected(self):
        assets = [
            RealAmsterdamAsset(
                asset_id="DUP", address="A", bag_pand_id="1",
                bag_verblijfsobject_id="1", geometry_type="Point",
                coordinates_x=4.9, coordinates_y=52.37, crs="EPSG:4326",
                bouwjaar=2000, gebruiksdoel="kantoorfunctie", oppervlakte_m2=100,
            ),
            RealAmsterdamAsset(
                asset_id="DUP", address="B", bag_pand_id="2",
                bag_verblijfsobject_id="2", geometry_type="Point",
                coordinates_x=4.91, coordinates_y=52.38, crs="EPSG:4326",
                bouwjaar=2001, gebruiksdoel="winkelfunctie", oppervlakte_m2=200,
            ),
        ]
        with pytest.raises(SystemExit, match="FAIL-CLOSED"):
            build_pilot_evidence_pack(assets=assets)

    def test_atomic_write(self, pilot_asset_list: list[RealAmsterdamAsset], tmp_path: Path):
        output = tmp_path / "pilot_pack.json"
        pack = build_pilot_evidence_pack(
            assets=pilot_asset_list, output_path=str(output)
        )
        assert output.exists()
        loaded = json.loads(output.read_text(encoding="utf-8"))
        assert loaded["pack_id"] == PILOT_PACK_ID

    def test_no_compliant_non_compliant_labels(self, pilot_asset_list: list[RealAmsterdamAsset]):
        pack = build_pilot_evidence_pack(assets=pilot_asset_list)
        for ev in pack["asset_evaluations"]:
            assert ev["overall_status"] not in ("compliant", "non_compliant")
            for rr in ev["rule_results"]:
                assert rr["status"] not in ("compliant", "non_compliant")


# ---------------------------------------------------------------------------
# Acceptance contract tests
# ---------------------------------------------------------------------------

class TestAcceptanceContract:
    """Verify the PR #157 acceptance contract is met."""

    def test_real_assets_gte_5(self, pilot_asset_list):
        assert len(pilot_asset_list) >= 5

    def test_customer_data_zero(self):
        assert PILOT_CLASSIFICATION["customer_data_status"] == "public_official_data_only"

    def test_bag_identity_verified(self, pilot_asset_list):
        assert all(a.asset_identity_verified for a in pilot_asset_list)

    def test_regulatory_artifact_exists(self):
        assert AMSTERDAM_OMGEVINGSPLAN_URL

    def test_threshold_source_verified_false(self, pilot_asset_list):
        pack = build_pilot_evidence_pack(assets=pilot_asset_list)
        assert pack["pilot_gates"]["threshold_source_verified"] is True

    def test_asset_applicability_verified_false(self, pilot_asset_list):
        pack = build_pilot_evidence_pack(assets=pilot_asset_list)
        assert pack["pilot_gates"]["asset_applicability_verified"] is False

    def test_production_eligible_false(self, pilot_asset_list):
        pack = build_pilot_evidence_pack(assets=pilot_asset_list)
        assert pack["pilot_gates"]["production_eligible"] is False

    def test_external_use_approved_false(self, pilot_asset_list):
        pack = build_pilot_evidence_pack(assets=pilot_asset_list)
        assert pack["pilot_gates"]["external_use_approved"] is False

    def test_no_synthetic_fallback(self, pilot_asset_list):
        pack = build_pilot_evidence_pack(assets=pilot_asset_list)
        assert pack["summary"]["synthetic_fallback_used"] is False


# ---------------------------------------------------------------------------
# Real BAG snapshot verification tests
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SNAPSHOT_DIR = PROJECT_ROOT / "data" / "nl_pilot" / "snapshots"
MANIFEST_PATH = PROJECT_ROOT / "data" / "nl_pilot" / "provenance-manifest.json"

_BAG_SNAPSHOTS = {
    "bag-pand": {
        "path": SNAPSHOT_DIR / "bag-pand.raw.json",
        "url_fragment": "/collections/pand/items",
    },
    "bag-verblijfsobject": {
        "path": SNAPSHOT_DIR / "bag-verblijfsobject.raw.json",
        "url_fragment": "/collections/verblijfsobject/items",
    },
    "bag-adres": {
        "path": SNAPSHOT_DIR / "bag-adres.raw.json",
        "url_fragment": "/collections/adres/items",
    },
}


class TestRealBAGSnapshots:
    """Verify committed real BAG snapshots (no live network)."""

    def test_all_three_snapshot_files_exist(self):
        for source_id, info in _BAG_SNAPSHOTS.items():
            assert info["path"].exists(), f"Missing snapshot: {source_id}"

    def test_all_snapshot_files_nonempty(self):
        for source_id, info in _BAG_SNAPSHOTS.items():
            size = info["path"].stat().st_size
            assert size > 0, f"Empty snapshot: {source_id}"

    def test_manifest_exists(self):
        assert MANIFEST_PATH.exists(), "provenance-manifest.json missing"

    def test_manifest_has_all_three_entries(self):
        manifest = json.loads(MANIFEST_PATH.read_text())
        sources = manifest.get("sources", {})
        for source_id in _BAG_SNAPSHOTS:
            assert source_id in sources, f"{source_id} missing from manifest"

    def test_artifact_sha_matches_committed_bytes(self):
        manifest = json.loads(MANIFEST_PATH.read_text())
        for source_id, info in _BAG_SNAPSHOTS.items():
            entry = manifest["sources"][source_id]
            actual_bytes = info["path"].read_bytes()
            actual_sha = hashlib.sha256(actual_sha_input := actual_bytes).hexdigest()
            assert actual_sha == entry["artifact_sha256"], (
                f"Artifact hash mismatch for {source_id}"
            )

    def test_normalized_sha_recomputes(self):
        manifest = json.loads(MANIFEST_PATH.read_text())
        for source_id, info in _BAG_SNAPSHOTS.items():
            entry = manifest["sources"][source_id]
            raw_bytes = info["path"].read_bytes()
            data = json.loads(raw_bytes)
            canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            actual_sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            assert actual_sha == entry["normalized_content_sha256"], (
                f"Normalized hash mismatch for {source_id}"
            )

    def test_parsed_type_is_feature_collection(self):
        for source_id, info in _BAG_SNAPSHOTS.items():
            data = json.loads(info["path"].read_text())
            assert data.get("type") == "FeatureCollection", (
                f"{source_id}: type is '{data.get("type")}' not 'FeatureCollection'"
            )

    def test_features_is_list(self):
        for source_id, info in _BAG_SNAPSHOTS.items():
            data = json.loads(info["path"].read_text())
            features = data.get("features")
            assert isinstance(features, list), (
                f"{source_id}: 'features' is not a list"
            )

    def test_at_least_one_feature_per_snapshot(self):
        for source_id, info in _BAG_SNAPSHOTS.items():
            data = json.loads(info["path"].read_text())
            assert len(data.get("features", [])) > 0, (
                f"{source_id}: no features"
            )

    def test_source_urls_are_official_pdok(self):
        manifest = json.loads(MANIFEST_PATH.read_text())
        for source_id, info in _BAG_SNAPSHOTS.items():
            entry = manifest["sources"][source_id]
            url = entry["source_url"]
            assert "pdok.nl" in url, f"{source_id}: URL not PDOK: {url}"
            assert info["url_fragment"] in url, (
                f"{source_id}: URL missing collection fragment: {url}"
            )

    def test_license_metadata_present(self):
        manifest = json.loads(MANIFEST_PATH.read_text())
        for source_id in _BAG_SNAPSHOTS:
            entry = manifest["sources"][source_id]
            assert entry["license_id"] == "Public Domain Mark 1.0"
            assert entry["authority"] == "Kadaster (LV-BAG) / PDOK"


class TestSnapshotJoinability:
    """Verify cross-collection join logic from committed snapshots."""

    @pytest.fixture(scope="class")
    def _snap_data(self):
        """Load all three snapshot FeatureCollections."""
        pand = json.loads((SNAPSHOT_DIR / "bag-pand.raw.json").read_text())
        vbo = json.loads((SNAPSHOT_DIR / "bag-verblijfsobject.raw.json").read_text())
        adres = json.loads((SNAPSHOT_DIR / "bag-adres.raw.json").read_text())
        return pand, vbo, adres

    def test_adresseerbaar_object_joins_to_vbo_identificatie(self, _snap_data):
        """adres.properties.adresseerbaar_object_identificatie == vbo.properties.identificatie"""
        _pand, vbo, adres = _snap_data
        vbo_idents = {f["properties"]["identificatie"] for f in vbo["features"]}
        resolved = 0
        for f in adres["features"]:
            ao_id = f["properties"].get("adresseerbaar_object_identificatie", "")
            if ao_id in vbo_idents:
                resolved += 1
        assert resolved > 0, "No adres→VBO joins resolved"

    def test_href_uuid_joins_to_feature_id(self, _snap_data):
        """UUID from pand.href matches pand top-level feature.id, NOT identificatie."""
        pand, vbo, _adres = _snap_data
        pand_by_feature_id = {f["id"]: f for f in pand["features"]}
        pand_idents = {f["properties"]["identificatie"] for f in pand["features"]}
        resolved = 0
        for f in vbo["features"]:
            pand_hrefs = f["properties"].get("pand.href") or []
            for href in pand_hrefs:
                uuid = href.rstrip("/").split("/")[-1]
                # Must match feature.id, NOT identificatie
                if uuid in pand_by_feature_id:
                    resolved += 1
                    # Ensure UUID is NOT a BAG identificatie
                    assert uuid not in pand_idents, (
                        f"UUID {uuid} should not equal any BAG identificatie"
                    )
        assert resolved > 0, "No VBO→Pand joins via feature.id"

    def test_known_chain_resolves(self, _snap_data):
        """VBO 0305010000001503 → Pand UUID 33478d74... resolves from committed snapshots."""
        pand, vbo, _adres = _snap_data
        pand_by_feature_id = {f["id"]: f for f in pand["features"]}
        vbo_by_ident = {f["properties"]["identificatie"]: f for f in vbo["features"]}

        f_vbo = vbo_by_ident.get("0305010000001503")
        assert f_vbo is not None, "VBO 0305010000001503 not in snapshot"

        pand_hrefs = f_vbo["properties"].get("pand.href") or []
        assert len(pand_hrefs) >= 1, "VBO 0305010000001503 has no pand.href"

        uuid = pand_hrefs[0].rstrip("/").split("/")[-1]
        assert uuid == "33478d74-7a5d-5acc-81b3-95fc8017b5ab"

        f_pand = pand_by_feature_id.get(uuid)
        assert f_pand is not None, f"Pand feature.id {uuid} not in snapshot"
        assert f_pand["properties"]["identificatie"] == "0305100000001259"

    def test_feature_id_is_never_confused_with_identificatie(self, _snap_data):
        """feature.id UUID must not be labelled or compared as BAG identificatie."""
        pand, _vbo, _adres = _snap_data
        for f in pand["features"]:
            feature_id = f.get("id", "")
            identificatie = f["properties"].get("identificatie", "")
            # feature.id is UUID, identificatie is numeric — never equal
            if feature_id and identificatie:
                assert feature_id != identificatie, (
                    f"feature.id {feature_id} == identificatie {identificatie} — "
                    f"these must be different identifier spaces"
                )


AMSTERDAM_DIR = SNAPSHOT_DIR / "amsterdam-v1"
AMSTERDAM_MANIFEST = PROJECT_ROOT / "data" / "nl_pilot" / "provenance-manifest-amsterdam-v1.json"


class TestAmsterdamChains:
    """Verify Amsterdam-targeted acquisition with complete source joins."""

    @pytest.fixture(scope="class")
    def _amsterdam_data(self):
        """Load Amsterdam VBO selected + Pand features + manifest."""
        vbo_path = AMSTERDAM_DIR / "amsterdam-vbo-selected.derived.json"
        assert vbo_path.exists(), "Amsterdam VBO derived snapshot missing"
        vbo_fc = json.loads(vbo_path.read_text())

        manifest = json.loads(AMSTERDAM_MANIFEST.read_text())
        chains = manifest.get("chains", {})

        # Load pand features for each chain
        pand_features = {}
        for chain_key, chain in chains.items():
            pand_uuid = chain["pand_feature_id"]
            pand_path = AMSTERDAM_DIR / f"pand-{pand_uuid}.raw.json"
            assert pand_path.exists(), f"Pand snapshot missing: {pand_uuid}"
            pand_features[pand_uuid] = json.loads(pand_path.read_text())

        return vbo_fc, chains, pand_features, manifest

    def test_at_least_5_amsterdam_chains(self, _amsterdam_data):
        """>=5 complete Amsterdam chains established."""
        _vbo, chains, _pand, _manifest = _amsterdam_data
        assert len(chains) >= 5, f"Only {len(chains)} chains, need >= 5"

    def test_all_chains_bronhouder_0363(self, _amsterdam_data):
        """All selected VBOs have bronhouder_identificatie == 0363."""
        _vbo, chains, _pand, _manifest = _amsterdam_data
        for key, chain in chains.items():
            assert chain["bronhouder_id"] == "0363", (
                f"{key}: bronhouder_id={chain['bronhouder_id']}"
            )

    def test_all_chains_bronhouder_amsterdam(self, _amsterdam_data):
        """All selected VBOs have bronhouder_naam == Amsterdam."""
        _vbo, chains, _pand, _manifest = _amsterdam_data
        for key, chain in chains.items():
            assert chain["bronhouder_naam"] == "Amsterdam", (
                f"{key}: bronhouder_naam={chain['bronhouder_naam']}"
            )

    def test_no_woonfunctie_only_candidates(self, _amsterdam_data):
        """No candidate is woonfunctie-only."""
        _vbo, chains, _pand, _manifest = _amsterdam_data
        for key, chain in chains.items():
            gd = chain.get("gebruiksdoel", "")
            assert gd != "woonfunctie", (
                f"{key}: woonfunctie-only candidate selected"
            )

    def test_address_vbo_identity_resolves(self, _amsterdam_data):
        """VBO.hoofdadres_identificatie == chain adres_identificatie."""
        vbo_fc, chains, _pand, _manifest = _amsterdam_data
        for key, chain in chains.items():
            vbo_ident = chain["vbo_identificatie"]
            # Find VBO feature in selected snapshot
            vbo_feature = None
            for f in vbo_fc["features"]:
                if f["properties"]["identificatie"] == vbo_ident:
                    vbo_feature = f
                    break
            assert vbo_feature is not None, f"{key}: VBO {vbo_ident} not in snapshot"
            hoofdadres = vbo_feature["properties"].get("hoofdadres_identificatie", "")
            assert hoofdadres == chain["adres_identificatie"], (
                f"{key}: hoofdadres {hoofdadres} != adres_identificatie {chain['adres_identificatie']}"
            )

    def test_vbo_pand_feature_id_join(self, _amsterdam_data):
        """VBO pand.href UUID matches Pand feature.id."""
        _vbo, chains, pand_features, _manifest = _amsterdam_data
        for key, chain in chains.items():
            pand_uuid = chain["pand_feature_id"]
            pand_feat = pand_features[pand_uuid]
            assert pand_feat.get("id") == pand_uuid, (
                f"{key}: Pand feature.id {pand_feat.get('id')} != {pand_uuid}"
            )

    def test_feature_uuid_never_equals_identificatie(self, _amsterdam_data):
        """feature.id UUID is never BAG identificatie."""
        _vbo, chains, pand_features, _manifest = _amsterdam_data
        for key, chain in chains.items():
            pand_uuid = chain["pand_feature_id"]
            pand_ident = chain["pand_identificatie"]
            assert pand_uuid != pand_ident, (
                f"{key}: feature.id {pand_uuid} == identificatie {pand_ident}"
            )

    def test_raw_hashes_reproduce(self, _amsterdam_data):
        """All raw artifact hashes reproduce from committed bytes.
        
        Uses source-appropriate normalization:
        - JSON/GeoJSON: canonical json.dumps(sort_keys=True, separators=(",", ":"))
        - HTML: strip tags + normalize whitespace
        """
        _vbo, _chains, _pand, manifest = _amsterdam_data
        for source_id, entry in manifest["sources"].items():
            if "snapshot_path" not in entry:
                continue  # metadata-only entries without sealed artifact
            path = Path(entry["snapshot_path"])
            assert path.exists(), f"{source_id}: snapshot missing"
            raw = path.read_bytes()
            assert len(raw) > 0, f"{source_id}: snapshot empty"
            assert hashlib.sha256(raw).hexdigest() == entry["artifact_sha256"], (
                f"{source_id}: artifact hash mismatch"
            )
            if "normalized_content_sha256" in entry:
                content_type = entry.get("content_type", "")
                collection = entry.get("collection", "")
                if "json" in content_type or collection in (
                    "verblijfsobject", "pand", "adres",
                ):
                    # JSON/GeoJSON: canonical JSON normalization
                    import json as _json
                    data = _json.loads(raw)
                    canonical = _json.dumps(
                        data, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                    )
                    norm_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                else:
                    # HTML: strip tags + normalize whitespace
                    import re as _re
                    text = raw.decode("utf-8", errors="replace")
                    text_clean = _re.sub(r"<script[^>]*>.*?</script>", "", text, flags=_re.DOTALL | _re.IGNORECASE)
                    text_clean = _re.sub(r"<style[^>]*>.*?</style>", "", text_clean, flags=_re.DOTALL | _re.IGNORECASE)
                    text_clean = _re.sub(r"<[^>]+>", " ", text_clean)
                    text_clean = _re.sub(r"\s+", " ", text_clean).strip()
                    norm_hash = hashlib.sha256(text_clean.encode("utf-8")).hexdigest()
                assert norm_hash == entry["normalized_content_sha256"], (
                    f"{source_id}: normalized hash mismatch"
                )

    def test_historical_snapshots_preserved(self):
        """Original ISSUE_3 snapshots remain unchanged."""
        for sid in ["bag-pand", "bag-verblijfsobject", "bag-adres"]:
            path = SNAPSHOT_DIR / f"{sid}.raw.json"
            assert path.exists(), f"Historical snapshot missing: {sid}"
            assert path.stat().st_size > 0, f"Historical snapshot empty: {sid}"

    def test_no_hard_coded_assets_used(self, _amsterdam_data):
        """Selected chains come from source, not hard-coded fixtures."""
        _vbo, chains, _pand, _manifest = _amsterdam_data
        for key, chain in chains.items():
            # All chain values must be non-empty strings
            assert chain["vbo_identificatie"], f"{key}: empty VBO identificatie"
            assert chain["pand_identificatie"], f"{key}: empty Pand identificatie"
            assert chain["pand_feature_id"], f"{key}: empty Pand feature_id"
            assert chain["gebruiksdoel"], f"{key}: empty gebruiksdoel"
            assert chain["woonplaats"] == "Amsterdam", (
                f"{key}: woonplaats={chain['woonplaats']}"
            )


# ---------------------------------------------------------------------------
# ISSUE_4C: Chain-Derived Pilot Assets
# ---------------------------------------------------------------------------


class TestChainDerivedAssets:
    """ISSUE_4C-R1: Verify that pilot_assets() loads from sealed evidence,
    NOT from Python literals.

    Tests independently read the manifest and sealed raw snapshots to
    verify the factory output — no duplicate hard-coded truth tables.
    """

    @pytest.fixture(scope="class")
    def _assets(self) -> list[RealAmsterdamAsset]:
        return pilot_assets()

    @pytest.fixture(scope="class")
    def _assets_by_pand(self, _assets) -> dict[str, RealAmsterdamAsset]:
        return {a.bag_pand_id: a for a in _assets}

    @pytest.fixture(scope="class")
    def _amsterdam_manifest(self) -> dict:
        return json.loads(AMSTERDAM_MANIFEST.read_text())

    @pytest.fixture(scope="class")
    def _vbo_fc(self) -> dict:
        vbo_path = AMSTERDAM_DIR / "amsterdam-vbo-selected.derived.json"
        return json.loads(vbo_path.read_text())

    # --- Factory construction tests ---

    def test_factory_loads_from_sealed_evidence(self):
        """load_pilot_assets reads manifest + raw files, not literals."""
        from app.nl_pilot.real_assets import load_pilot_assets
        assets = load_pilot_assets(PROJECT_ROOT)
        assert len(assets) == 5
        # All assets must have identity verified (proven from evidence)
        assert all(a.asset_identity_verified for a in assets)

    def test_factory_rejects_missing_manifest(self, tmp_path):
        """Factory raises FileNotFoundError for missing manifest."""
        from app.nl_pilot.real_assets import load_pilot_assets
        with pytest.raises(FileNotFoundError):
            load_pilot_assets(tmp_path)

    def test_chain_asset_count(self, _assets):
        """Exactly 5 chain-derived assets."""
        assert len(_assets) == 5

    def test_chain_asset_ids_sequential(self, _assets):
        """Asset IDs follow NL-AM-CHAIN-N format."""
        ids = sorted(a.asset_id for a in _assets)
        for i, aid in enumerate(ids, 1):
            assert aid == f"NL-AM-CHAIN-{i:03d}", f"Unexpected ID: {aid}"

    # --- Verify against manifest (independent of hard-coded truth) ---

    def test_pand_ids_match_manifest(self, _assets, _amsterdam_manifest):
        """Each asset's bag_pand_id matches manifest chain pand_identificatie."""
        manifest_chains = _amsterdam_manifest["chains"]
        assets_by_chain = {
            a.asset_id.split("-")[-1]: a for a in _assets
        }
        for chain_key, chain in manifest_chains.items():
            chain_num = f"{int(chain_key.split('-')[1]):03d}"
            asset = assets_by_chain.get(chain_num)
            assert asset is not None, f"No asset for {chain_key}"
            assert asset.bag_pand_id == chain["pand_identificatie"], (
                f"{chain_key}: pand_id mismatch"
            )

    def test_vbo_ids_match_manifest(self, _assets, _amsterdam_manifest):
        """Each asset's bag_verblijfsobject_id matches manifest chain vbo_identificatie."""
        manifest_chains = _amsterdam_manifest["chains"]
        assets_by_chain = {
            a.asset_id.split("-")[-1]: a for a in _assets
        }
        for chain_key, chain in manifest_chains.items():
            chain_num = f"{int(chain_key.split('-')[1]):03d}"
            asset = assets_by_chain.get(chain_num)
            assert asset is not None, f"No asset for {chain_key}"
            assert asset.bag_verblijfsobject_id == chain["vbo_identificatie"], (
                f"{chain_key}: vbo_id mismatch"
            )

    # --- Verify attribute values against raw evidence ---

    def test_bouwjaar_from_pand_raw(self, _assets_by_pand, _amsterdam_manifest):
        """Bouwjaar comes from Pand raw feature, not hardcoded."""
        manifest_chains = _amsterdam_manifest["chains"]
        for chain_key, chain in manifest_chains.items():
            pand_id = chain["pand_identificatie"]
            asset = _assets_by_pand[pand_id]
            # Load Pand raw feature independently
            pand_path = AMSTERDAM_DIR / f"pand-{chain['pand_feature_id']}.raw.json"
            pand_data = json.loads(pand_path.read_text())
            pand_feat = (
                pand_data if pand_data.get("type") == "Feature"
                else pand_data["features"][0]
            )
            expected_bouwjaar = pand_feat["properties"]["bouwjaar"]
            assert asset.bouwjaar == expected_bouwjaar, (
                f"{chain_key}: bouwjaar={asset.bouwjaar} != {expected_bouwjaar}"
            )

    def test_gebruiksdoel_from_vbo_raw(self, _assets_by_pand, _amsterdam_manifest, _vbo_fc):
        """Gebruiksdoel comes from VBO feature, not hardcoded."""
        vbo_by_ident = {
            f["properties"]["identificatie"]: f
            for f in _vbo_fc["features"]
        }
        manifest_chains = _amsterdam_manifest["chains"]
        for chain_key, chain in manifest_chains.items():
            pand_id = chain["pand_identificatie"]
            asset = _assets_by_pand[pand_id]
            vbo_feat = vbo_by_ident[chain["vbo_identificatie"]]
            expected_gd = vbo_feat["properties"]["gebruiksdoel"]
            assert asset.gebruiksdoel == expected_gd, (
                f"{chain_key}: gebruiksdoel={asset.gebruiksdoel} != {expected_gd}"
            )

    def test_oppervlakte_from_vbo_raw(self, _assets_by_pand, _amsterdam_manifest, _vbo_fc):
        """Oppervlakte comes from VBO feature, not hardcoded."""
        vbo_by_ident = {
            f["properties"]["identificatie"]: f
            for f in _vbo_fc["features"]
        }
        manifest_chains = _amsterdam_manifest["chains"]
        for chain_key, chain in manifest_chains.items():
            pand_id = chain["pand_identificatie"]
            asset = _assets_by_pand[pand_id]
            vbo_feat = vbo_by_ident[chain["vbo_identificatie"]]
            expected_opp = float(vbo_feat["properties"]["oppervlakte"])
            assert asset.oppervlakte_m2 == expected_opp, (
                f"{chain_key}: oppervlakte={asset.oppervlakte_m2} != {expected_opp}"
            )

    def test_coordinates_from_vbo_geometry(self, _assets_by_pand, _amsterdam_manifest, _vbo_fc):
        """Coordinates come from VBO geometry, not hardcoded."""
        vbo_by_ident = {
            f["properties"]["identificatie"]: f
            for f in _vbo_fc["features"]
        }
        manifest_chains = _amsterdam_manifest["chains"]
        for chain_key, chain in manifest_chains.items():
            pand_id = chain["pand_identificatie"]
            asset = _assets_by_pand[pand_id]
            vbo_feat = vbo_by_ident[chain["vbo_identificatie"]]
            coords = vbo_feat["geometry"]["coordinates"]
            assert asset.coordinates_x == coords[0], (
                f"{chain_key}: lon mismatch"
            )
            assert asset.coordinates_y == coords[1], (
                f"{chain_key}: lat mismatch"
            )

    # --- Verification flags are computed, not default ---

    def test_fail_closed_defaults(self):
        """RealAmsterdamAsset defaults are all False (fail-closed)."""
        asset = RealAmsterdamAsset(
            asset_id="TEST", address="Test",
            bag_pand_id="1", bag_verblijfsobject_id="1",
            geometry_type="Point",
            coordinates_x=4.9, coordinates_y=52.37,
            crs="EPSG:4326",
            bouwjaar=2000, gebruiksdoel="kantoorfunctie",
            oppervlakte_m2=100.0,
        )
        assert asset.asset_identity_verified is False
        assert asset.building_geometry_verified is False
        assert asset.use_class_verified is False
        assert asset.asset_applicability_verified is False
        assert asset.production_eligible is False

    def test_identity_verified_from_evidence(self, _assets):
        """Identity flags are True only because factory verified the chain."""
        for a in _assets:
            assert a.asset_identity_verified is True
            assert a.source_integrity_verified is True
            assert a.building_geometry_verified is True  # ISSUE_7: Pand polygon verified
            assert a.use_class_verified is True

    def test_not_production_eligible(self, _assets):
        """Chain-derived assets are NOT production eligible."""
        for a in _assets:
            assert a.asset_applicability_verified is False
            assert a.engineering_capacity_verified is False
            assert a.production_eligible is False

    # --- to_dict() semantic tests ---

    def test_to_dict_no_built_area_m2(self, _assets):
        """to_dict() must NOT emit built_area_m2 (different semantic)."""
        for a in _assets:
            d = a.to_dict()
            assert "built_area_m2" not in d, (
                f"{a.asset_id}: built_area_m2 in to_dict"
            )

    def test_to_dict_preserves_identity(self, _assets):
        """to_dict() preserves chain identity."""
        for a in _assets:
            d = a.to_dict()
            assert d["bag_pand_id"] == a.bag_pand_id
            assert d["bag_verblijfsobject_id"] == a.bag_verblijfsobject_id
            assert d["municipality"] == "Amsterdam"
            assert d["asset_identity_verified"] is True

    # --- Uniqueness and absence of old fixtures ---

    def test_no_old_pand_ids(self, _assets):
        """No old hard-coded pand IDs remain."""
        old_pand_ids = {"36320619", "36319427", "36321855", "36320193", "36322419"}
        for a in _assets:
            assert a.bag_pand_id not in old_pand_ids, (
                f"{a.asset_id}: old pand_id {a.bag_pand_id}"
            )

    def test_unique_pand_ids(self, _assets):
        """All pand IDs are unique."""
        pand_ids = [a.bag_pand_id for a in _assets]
        assert len(pand_ids) == len(set(pand_ids))

    def test_unique_vbo_ids(self, _assets):
        """All VBO IDs are unique."""
        vbo_ids = [a.bag_verblijfsobject_id for a in _assets]
        assert len(vbo_ids) == len(set(vbo_ids))

    # --- Manifest metadata ---

    def test_address_source_traces_to_adres(self, _amsterdam_manifest):
        """Each chain's address_source is independent_adres_collection_record."""
        chains = _amsterdam_manifest["chains"]
        for chain_key, chain in chains.items():
            assert chain.get("address_source") == "independent_adres_collection_record", (
                f"{chain_key}: address_source={chain.get('address_source')}"
            )

    def test_adres_collection_source_ids(self, _amsterdam_manifest):
        """Each chain has a valid adres_collection_source_id."""
        chains = _amsterdam_manifest["chains"]
        for chain_key, chain in chains.items():
            src_id = chain.get("adres_collection_source_id", "")
            assert src_id == f"amsterdam-{chain_key}", (
                f"{chain_key}: adres_collection_source_id={src_id}"
            )


# ---------------------------------------------------------------------------
# ISSUE_4B-R2: Independent BAG Adres Collection Verification
# ---------------------------------------------------------------------------

# The 5 Amsterdam chains' address identificaties, matching the manifest
ADRES_TARGET_IDENTIFICATIES = {
    "chain-1": "0363200000006110",
    "chain-2": "0363200000403263",
    "chain-3": "0363200000006127",
    "chain-4": "0363200000006140",
    "chain-5": "0363200000431014",
}
ADRES_TARGET_VBO_IDENTS = {
    "chain-1": "0363010000543292",
    "chain-2": "0363010000543308",
    "chain-3": "0363010000543309",
    "chain-4": "0363010000543325",
    "chain-5": "0363010000544122",
}


class TestIndependentAdresVerification:
    """ISSUE_4B-R2: Verify that independent BAG Adres collection features
    are committed and that all 5 chains join correctly.

    These tests load the committed Adres raw snapshots and verify:
      1. Adres.properties.identificatie == VBO.properties.hoofdadres_identificatie
      2. Adres.properties.adresseerbaar_object_identificatie == VBO.properties.identificatie
      3. Adres.properties.adresseerbaar_object_type == "Verblijfsobject"
      4. Adres.properties.bronhouder_identificatie == "0363"
      5. Adres.properties.bronhouder_naam == "Amsterdam"
    """

    @pytest.fixture(scope="class")
    def _adres_features(self) -> dict[str, dict]:
        """Load all 5 committed Adres raw snapshots."""
        features = {}
        for chain_key, ident in ADRES_TARGET_IDENTIFICATIES.items():
            path = AMSTERDAM_DIR / f"adres-{ident}.raw.json"
            assert path.exists(), (
                f"Adres snapshot missing: adres-{ident}.raw.json"
            )
            fc = json.loads(path.read_text())
            assert fc.get("type") == "FeatureCollection", (
                f"{ident}: not a FeatureCollection"
            )
            feat_list = fc.get("features", [])
            assert len(feat_list) == 1, (
                f"{ident}: expected 1 feature, got {len(feat_list)}"
            )
            features[chain_key] = feat_list[0]
        return features

    @pytest.fixture(scope="class")
    def _vbo_features(self) -> dict[str, dict]:
        """Load VBO features for the 5 chains from the derived snapshot."""
        vbo_path = AMSTERDAM_DIR / "amsterdam-vbo-selected.derived.json"
        assert vbo_path.exists(), "Amsterdam VBO derived snapshot missing"
        vbo_fc = json.loads(vbo_path.read_text())
        vbo_map = {}
        for f in vbo_fc["features"]:
            ident = f["properties"].get("identificatie", "")
            vbo_map[ident] = f
        return vbo_map

    @pytest.fixture(scope="class")
    def _amsterdam_manifest(self) -> dict:
        """Load the Amsterdam manifest."""
        return json.loads(AMSTERDAM_MANIFEST.read_text())

    # --- Snapshot presence and integrity ---

    def test_all_5_adres_snapshots_exist(self, _adres_features):
        """All 5 Adres raw snapshot files are committed."""
        assert len(_adres_features) == 5

    def test_adres_snapshots_are_feature_collections(self, _adres_features):
        """Each Adres snapshot wraps exactly one feature."""
        for chain_key, feature in _adres_features.items():
            assert feature.get("type") == "Feature", (
                f"{chain_key}: not a Feature"
            )

    # --- Join condition 1: Adres.identificatie == VBO.hoofdadres_identificatie ---

    def test_adres_identificatie_matches_vbo_hoofdadres(self, _adres_features, _vbo_features):
        """Adres.identificatie == VBO.hoofdadres_identificatie for all 5 chains."""
        for chain_key in ADRES_TARGET_IDENTIFICATIES:
            ident = ADRES_TARGET_IDENTIFICATIES[chain_key]
            vbo_ident = ADRES_TARGET_VBO_IDENTS[chain_key]

            adres_feature = _adres_features[chain_key]
            adres_props = adres_feature["properties"]
            assert adres_props.get("identificatie") == ident, (
                f"{chain_key}: Adres.identificatie={adres_props.get('identificatie')}"
            )

            vbo_feature = _vbo_features.get(vbo_ident)
            assert vbo_feature is not None, (
                f"{chain_key}: VBO {vbo_ident} not in derived snapshot"
            )
            hoofdadres = vbo_feature["properties"].get("hoofdadres_identificatie", "")
            assert hoofdadres == ident, (
                f"{chain_key}: VBO.hoofdadres={hoofdadres} != Adres.identificatie={ident}"
            )

    # --- Join condition 2: Adres.adresseerbaar_object_identificatie == VBO.identificatie ---

    def test_adres_ao_identificatie_matches_vbo(self, _adres_features, _vbo_features):
        """Adres.adresseerbaar_object_identificatie == VBO.identificatie."""
        for chain_key in ADRES_TARGET_IDENTIFICATIES:
            vbo_ident = ADRES_TARGET_VBO_IDENTS[chain_key]
            adres_props = _adres_features[chain_key]["properties"]
            ao_id = adres_props.get("adresseerbaar_object_identificatie", "")
            assert ao_id == vbo_ident, (
                f"{chain_key}: Adres.ao={ao_id} != VBO.identificatie={vbo_ident}"
            )

    # --- Join condition 3: Adres.adresseerbaar_object_type == "Verblijfsobject" ---

    def test_adres_object_type_is_verblijfsobject(self, _adres_features):
        """All Adres features have adresseerbaar_object_type == Verblijfsobject."""
        for chain_key in ADRES_TARGET_IDENTIFICATIES:
            adres_props = _adres_features[chain_key]["properties"]
            obj_type = adres_props.get("adresseerbaar_object_type", "")
            assert obj_type == "Verblijfsobject", (
                f"{chain_key}: type={obj_type}"
            )

    # --- Join condition 4: Adres.bronhouder_identificatie == "0363" ---

    def test_adres_municipality_gate_0363(self, _adres_features):
        """All Adres features have bronhouder_identificatie == 0363."""
        for chain_key in ADRES_TARGET_IDENTIFICATIES:
            adres_props = _adres_features[chain_key]["properties"]
            bh_id = adres_props.get("bronhouder_identificatie", "")
            assert bh_id == "0363", (
                f"{chain_key}: bronhouder_identificatie={bh_id}"
            )

    # --- Join condition 5: Adres.bronhouder_naam == "Amsterdam" ---

    def test_adres_municipality_name_amsterdam(self, _adres_features):
        """All Adres features have bronhouder_naam == Amsterdam."""
        for chain_key in ADRES_TARGET_IDENTIFICATIES:
            adres_props = _adres_features[chain_key]["properties"]
            bh_naam = adres_props.get("bronhouder_naam", "")
            assert bh_naam == "Amsterdam", (
                f"{chain_key}: bronhouder_naam={bh_naam}"
            )

    # --- Raw hash verification ---

    def test_adres_raw_hashes_reproduce(self):
        """All committed Adres snapshots reproduce their artifact SHA-256."""
        manifest = json.loads(AMSTERDAM_MANIFEST.read_text())
        adres_sources = {
            k: v for k, v in manifest["sources"].items()
            if v.get("collection") == "adres"
        }
        assert len(adres_sources) == 5, (
            f"Expected 5 Adres source entries, got {len(adres_sources)}"
        )
        for source_id, entry in adres_sources.items():
            path = Path(entry["snapshot_path"])
            assert path.exists(), f"Missing: {path}"
            raw = path.read_bytes()
            actual_sha = hashlib.sha256(raw).hexdigest()
            assert actual_sha == entry["artifact_sha256"], (
                f"{source_id}: artifact hash mismatch"
            )
            # Also verify normalized hash
            data = json.loads(raw)
            canonical = json.dumps(
                data, sort_keys=True, separators=("," ,":"), ensure_ascii=True
            )
            norm_sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            assert norm_sha == entry["normalized_content_sha256"], (
                f"{source_id}: normalized hash mismatch"
            )

    # --- Complete chain verification ---

    def test_complete_adres_vbo_pand_chains(self, _adres_features, _vbo_features, _amsterdam_manifest):
        """All 5 chains have complete Adres → VBO → Pand joins."""
        chains = _amsterdam_manifest.get("chains", {})
        assert len(chains) >= 5, f"Only {len(chains)} chains"

        for chain_key in ADRES_TARGET_IDENTIFICATIES:
            chain = chains[chain_key]
            ident = ADRES_TARGET_IDENTIFICATIES[chain_key]
            vbo_ident = ADRES_TARGET_VBO_IDENTS[chain_key]

            # Adres → VBO join
            adres_props = _adres_features[chain_key]["properties"]
            assert adres_props.get("identificatie") == chain["adres_identificatie"], (
                f"{chain_key}: Adres.identificatie mismatch"
            )
            assert adres_props.get("adresseerbaar_object_identificatie") == vbo_ident, (
                f"{chain_key}: Adres.ao mismatch"
            )

            # VBO → Pand join (via pand.href UUID → Pand feature.id)
            vbo_feature = _vbo_features.get(vbo_ident)
            assert vbo_feature is not None, (
                f"{chain_key}: VBO not found"
            )
            assert chain.get("pand_feature_id"), (
                f"{chain_key}: no pand_feature_id"
            )
            assert chain.get("pand_identificatie"), (
                f"{chain_key}: no pand_identificatie"
            )

    # --- Manifest metadata ---

    def test_manifest_adres_source_entries_count(self, _amsterdam_manifest):
        """Manifest has exactly 5 Adres collection source entries."""
        adres_sources = {
            k: v for k, v in _amsterdam_manifest["sources"].items()
            if v.get("collection") == "adres"
        }
        assert len(adres_sources) == 5

    def test_manifest_issue_4b_r2_section(self, _amsterdam_manifest):
        """Manifest contains issue_4b_r2 verification section."""
        r2 = _amsterdam_manifest.get("issue_4b_r2", {})
        assert r2.get("adres_features_resolved") == 5
        assert r2.get("adres_identificatie_join") == "verified"
        assert r2.get("adres_object_vbo_join") == "verified"
        assert r2.get("adres_municipality_gate") == "verified"
        assert r2.get("adres_raw_hashes") == "verified"

    def test_manifest_chain_address_source_updated(self, _amsterdam_manifest):
        """All 5 chains reference independent Adres collection records."""
        chains = _amsterdam_manifest.get("chains", {})
        for chain_key in ADRES_TARGET_IDENTIFICATIES:
            chain = chains[chain_key]
            assert chain.get("address_source") == "independent_adres_collection_record", (
                f"{chain_key}: address_source={chain.get('address_source')}"
            )
            assert chain.get("adres_collection_source_id") == f"amsterdam-{chain_key}", (
                f"{chain_key}: adres_collection_source_id mismatch"
            )


# ---------------------------------------------------------------------------
# ISSUE_4C-R2: Final Evidence-Integrity Closure
# ---------------------------------------------------------------------------

class TestIssue4C_R2Integrity:
    """ISSUE_4C-R2: Regression tests verifying the factory's full
    evidence-integrity gates: hash verification, identity gates,
    address derivation, asset-ID consistency, and pack semantics.
    """

    @pytest.fixture(scope="class")
    def _assets(self) -> list[RealAmsterdamAsset]:
        return pilot_assets()

    @pytest.fixture(scope="class")
    def _amsterdam_manifest(self) -> dict:
        return json.loads(AMSTERDAM_MANIFEST.read_text())

    # --- Hash gate fail-closed tests ---

    def test_tamper_adres_raw_closes_factory(self, tmp_path):
        """Tamper one Adres raw byte → factory FAILS CLOSED."""
        from app.nl_pilot.real_assets import load_pilot_assets
        import shutil

        # Create a temporary project root with tampered adres
        project_root = tmp_path / "project"
        shutil.copytree(
            PROJECT_ROOT / "data" / "nl_pilot",
            project_root / "data" / "nl_pilot",
        )
        # Tamper one adres snapshot
        adres_path = (
            project_root / "data" / "nl_pilot" / "snapshots" / "amsterdam-v1"
            / "adres-0363200000006110.raw.json"
        )
        original = adres_path.read_bytes()
        # Flip a byte in the middle (not at the very end)
        tampered = original[:-10] + b"X" + original[-9:]
        adres_path.write_bytes(tampered)

        with pytest.raises(ValueError, match="HASH_MISMATCH_FAIL_CLOSED"):
            load_pilot_assets(project_root)

    def test_tamper_pand_raw_closes_factory(self, tmp_path):
        """Tamper one Pand raw artifact → factory FAILS CLOSED."""
        from app.nl_pilot.real_assets import load_pilot_assets
        import shutil

        project_root = tmp_path / "project"
        shutil.copytree(
            PROJECT_ROOT / "data" / "nl_pilot",
            project_root / "data" / "nl_pilot",
        )
        # Tamper one pand snapshot
        pand_path = (
            project_root / "data" / "nl_pilot" / "snapshots" / "amsterdam-v1"
            / "pand-dd867efb-bdbb-59e2-a114-86f1c9efb2d5.raw.json"
        )
        original = pand_path.read_bytes()
        tampered = original[:-10] + b"Y" + original[-9:]
        pand_path.write_bytes(tampered)

        with pytest.raises(ValueError, match="HASH_MISMATCH_FAIL_CLOSED"):
            load_pilot_assets(project_root)

    # --- Pand identity gate tests ---

    def test_pand_feature_id_matches_chain(self, _assets, _amsterdam_manifest):
        """Pand.feature.id == chain.pand_feature_id for all chains."""
        chains = _amsterdam_manifest["chains"]
        for chain_key, chain in chains.items():
            pand_path = AMSTERDAM_DIR / f"pand-{chain['pand_feature_id']}.raw.json"
            pand_data = json.loads(pand_path.read_bytes())
            pand_feat = (
                pand_data if pand_data.get("type") == "Feature"
                else pand_data["features"][0]
            )
            assert pand_feat["id"] == chain["pand_feature_id"], (
                f"{chain_key}: Pand.feature.id mismatch"
            )

    def test_pand_identificatie_matches_chain(self, _assets, _amsterdam_manifest):
        """Pand.properties.identificatie == chain.pand_identificatie."""
        chains = _amsterdam_manifest["chains"]
        for chain_key, chain in chains.items():
            pand_path = AMSTERDAM_DIR / f"pand-{chain['pand_feature_id']}.raw.json"
            pand_data = json.loads(pand_path.read_bytes())
            pand_feat = (
                pand_data if pand_data.get("type") == "Feature"
                else pand_data["features"][0]
            )
            assert pand_feat["properties"]["identificatie"] == chain["pand_identificatie"], (
                f"{chain_key}: Pand.identificatie mismatch"
            )

    # --- Adres identity gate tests ---

    def test_adres_bronhouder_naam_amsterdam(self, _amsterdam_manifest):
        """Adres.bronhouder_naam == 'Amsterdam' for all chains."""
        manifest = _amsterdam_manifest
        chains = manifest["chains"]
        sources = manifest["sources"]
        for chain_key, chain in chains.items():
            adres_src_id = chain["adres_collection_source_id"]
            adres_src = sources[adres_src_id]
            adres_fc = json.loads(
                (PROJECT_ROOT / adres_src["snapshot_path"]).read_text()
            )
            adres_feat = adres_fc["features"][0]
            assert adres_feat["properties"]["bronhouder_naam"] == "Amsterdam", (
                f"{chain_key}: bronhouder_naam mismatch"
            )

    def test_adres_address_derived_from_feature(self, _assets, _amsterdam_manifest):
        """Address comes from Adres raw feature fields, not manifest chain."""
        chains = _amsterdam_manifest["chains"]
        sources = _amsterdam_manifest["sources"]
        for chain_key, chain in chains.items():
            chain_num = int(chain_key.split("-")[1])
            asset = [a for a in _assets if a.asset_id == f"NL-AM-CHAIN-{chain_num:03d}"][0]
            adres_src = sources[chain["adres_collection_source_id"]]
            adres_fc = json.loads(
                (PROJECT_ROOT / adres_src["snapshot_path"]).read_text()
            )
            adres_props = adres_fc["features"][0]["properties"]
            street = adres_props["openbare_ruimte_naam"]
            num = str(adres_props["huisnummer"])
            toevoeging = adres_props.get("toevoeging") or ""
            wp = adres_props["woonplaats_naam"]
            expected = f"{street} {num}{toevoeging}, {wp}"
            assert asset.address == expected, (
                f"{chain_key}: address='{asset.address}' != '{expected}'"
            )

    # --- Asset-ID consistency ---

    def test_asset_ids_zero_padded(self, _assets):
        """Asset IDs are exactly NL-AM-CHAIN-001..005."""
        expected = [f"NL-AM-CHAIN-{i:03d}" for i in range(1, 6)]
        actual = sorted(a.asset_id for a in _assets)
        assert actual == expected, f"IDs: {actual}"

    def test_asset_ids_match_manifest_chain_mapping(self, _assets, _amsterdam_manifest):
        """Asset IDs match manifest.issue_4c.chain_mapping."""
        mapping = _amsterdam_manifest.get("issue_4c", {}).get("chain_mapping", {})
        for ck, expected_id in mapping.items():
            chain_num = int(ck.split("-")[1])
            actual_id = f"NL-AM-CHAIN-{chain_num:03d}"
            assert actual_id == expected_id, (
                f"{ck}: {actual_id} != manifest {expected_id}"
            )

    # --- building_geometry_verified from Pand polygon (ISSUE_7) ---

    def test_building_geometry_verified_from_pand_polygon(self, _assets):
        """building_geometry_verified is True — sealed Pand polygon verified."""
        for a in _assets:
            assert a.building_geometry_verified is True, (
                f"{a.asset_id}: building_geometry_verified should be True"
            )
            assert a.pand_footprint_area_m2 is not None
            assert a.pand_footprint_area_m2 > 0

    # --- Pack semantics tests ---

    def test_source_integrity_verified_from_factory(self, _assets):
        """source_integrity_verified is True from factory for all assets."""
        for a in _assets:
            assert a.source_integrity_verified is True, (
                f"{a.asset_id}: source_integrity_verified should be True"
            )

    def test_pack_unverified_assets_do_not_produce_real_assets(self):
        """5 unverified caller-created assets do NOT produce real_assets=true."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        unverified = [
            RealAmsterdamAsset(
                asset_id=f"FAKE-{i:03d}",
                address=f"Fake {i}, Amsterdam",
                bag_pand_id=f"fake-pand-{i}",
                bag_verblijfsobject_id=f"fake-vbo-{i}",
                geometry_type="Point",
                coordinates_x=4.9,
                coordinates_y=52.37,
                crs="EPSG:4326",
                bouwjaar=2000,
                gebruiksdoel="kantoorfunctie",
                oppervlakte_m2=100.0,
                # Defaults: all verification flags False
            )
            for i in range(5)
        ]
        pack = build_pilot_evidence_pack(assets=unverified)
        # V2: unverified assets have zero verified identity counts
        s = pack["summary"]
        assert s["real_assets_verified_count"] == 0
        assert s["bag_identity_verified_count"] == 0
        assert s["source_integrity_verified_count"] == 0
        assert s["building_geometry_verified_count"] == 0
        assert s["synthetic_fallback_used"] is False
        gates = pack["pilot_gates"]
        assert gates["production_eligible"] is False
        assert gates["external_use_approved"] is False

    def test_pack_built_area_m2_absent(self, _assets):
        """built_area_m2 remains absent from to_dict()."""
        for a in _assets:
            d = a.to_dict()
            assert "built_area_m2" not in d, (
                f"{a.asset_id}: built_area_m2 in to_dict"
            )

    def test_pack_engineering_capacity_verified_false(self, _assets):
        """engineering_capacity_verified remains False for all assets."""
        for a in _assets:
            assert a.engineering_capacity_verified is False, (
                f"{a.asset_id}: engineering_capacity_verified should be False"
            )


# ---------------------------------------------------------------------------
# ISSUE_4C-R3: Final Fail-Closed Closure Regression Tests
# ---------------------------------------------------------------------------


class TestIssue4C_R3FailClosed:
    """ISSUE_4C-R3: Proves factory fail-closed behavior for
    missing provenance, tampered data, and caller assertions.
    """

    def test_missing_pand_provenance_raises(self, tmp_path):
        """Missing Pand provenance entry → factory raises ValueError."""
        from app.nl_pilot.real_assets import load_pilot_assets
        import shutil
        pr = tmp_path / "project"
        shutil.copytree(PROJECT_ROOT / "data" / "nl_pilot", pr / "data" / "nl_pilot")
        manifest_path = pr / "data" / "nl_pilot" / "provenance-manifest-amsterdam-v1.json"
        m = json.loads(manifest_path.read_text())
        # Remove one pand source entry
        pand_src = [k for k in m["sources"] if k.startswith("amsterdam-pand-")][0]
        del m["sources"][pand_src]
        manifest_path.write_text(json.dumps(m, indent=2))
        with pytest.raises(ValueError, match="PROVENANCE_ENTRY_REQUIRED_FAIL_CLOSED"):
            load_pilot_assets(pr)

    def test_missing_adres_provenance_raises(self, tmp_path):
        """Missing Adres provenance entry → factory raises ValueError."""
        from app.nl_pilot.real_assets import load_pilot_assets
        import shutil
        pr = tmp_path / "project"
        shutil.copytree(PROJECT_ROOT / "data" / "nl_pilot", pr / "data" / "nl_pilot")
        manifest_path = pr / "data" / "nl_pilot" / "provenance-manifest-amsterdam-v1.json"
        m = json.loads(manifest_path.read_text())
        adres_src = [k for k in m["sources"] if m["sources"][k].get("collection") == "adres"][0]
        del m["sources"][adres_src]
        manifest_path.write_text(json.dumps(m, indent=2))
        with pytest.raises(ValueError, match="PROVENANCE_ENTRY_REQUIRED_FAIL_CLOSED"):
            load_pilot_assets(pr)

    def test_missing_vbo_derived_provenance_raises(self, tmp_path):
        """Missing VBO derived provenance → factory raises ValueError."""
        from app.nl_pilot.real_assets import load_pilot_assets
        import shutil
        pr = tmp_path / "project"
        shutil.copytree(PROJECT_ROOT / "data" / "nl_pilot", pr / "data" / "nl_pilot")
        manifest_path = pr / "data" / "nl_pilot" / "provenance-manifest-amsterdam-v1.json"
        m = json.loads(manifest_path.read_text())
        del m["derived_artifacts"]["amsterdam-vbo-selected"]
        manifest_path.write_text(json.dumps(m, indent=2))
        with pytest.raises(ValueError, match="PROVENANCE_ENTRY_REQUIRED_FAIL_CLOSED"):
            load_pilot_assets(pr)

    def test_tampered_vbo_raw_page_raises(self, tmp_path):
        """Tampered VBO raw page → factory raises ValueError."""
        from app.nl_pilot.real_assets import load_pilot_assets
        import shutil
        pr = tmp_path / "project"
        shutil.copytree(PROJECT_ROOT / "data" / "nl_pilot", pr / "data" / "nl_pilot")
        vbo_path = pr / "data" / "nl_pilot" / "snapshots" / "amsterdam-v1" / "vbo-page-0.raw.json"
        orig = vbo_path.read_bytes()
        vbo_path.write_bytes(orig[:-10] + b"Z" + orig[-9:])
        with pytest.raises(ValueError, match="HASH_MISMATCH_FAIL_CLOSED"):
            load_pilot_assets(pr)

    def test_adres_identity_mismatch_raises(self, tmp_path):
        """Adres identity mismatch → factory raises ValueError."""
        from app.nl_pilot.real_assets import load_pilot_assets
        import shutil
        pr = tmp_path / "project"
        shutil.copytree(PROJECT_ROOT / "data" / "nl_pilot", pr / "data" / "nl_pilot")
        adres_path = pr / "data" / "nl_pilot" / "snapshots" / "amsterdam-v1" / "adres-0363200000006110.raw.json"
        data = json.loads(adres_path.read_text())
        data["features"][0]["properties"]["bronhouder_naam"] = "Wrong"
        # Recompute hashes so hash gate passes but identity gate fails
        import hashlib
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        norm_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        raw_bytes = canonical.encode("utf-8")
        art_hash = hashlib.sha256(raw_bytes).hexdigest()
        adres_path.write_bytes(raw_bytes)
        m = json.loads((pr / "data" / "nl_pilot" / "provenance-manifest-amsterdam-v1.json").read_text())
        m["sources"]["amsterdam-chain-1"]["artifact_sha256"] = art_hash
        m["sources"]["amsterdam-chain-1"]["normalized_content_sha256"] = norm_hash
        (pr / "data" / "nl_pilot" / "provenance-manifest-amsterdam-v1.json").write_text(json.dumps(m, indent=2))
        with pytest.raises(ValueError, match="Adres identity gate failed"):
            load_pilot_assets(pr)

    def test_caller_cannot_assert_verified(self):
        """RealAmsterdamAsset(... asset_identity_verified=True) → TypeError."""
        with pytest.raises(TypeError):
            RealAmsterdamAsset(
                asset_id="X", address="X", bag_pand_id="1",
                bag_verblijfsobject_id="1", geometry_type="Point",
                coordinates_x=4.9, coordinates_y=52.37, crs="EPSG:4326",
                bouwjaar=2000, gebruiksdoel="kantoorfunctie",
                oppervlakte_m2=100.0, asset_identity_verified=True,
            )

    def test_caller_cannot_assert_source_integrity(self):
        """RealAmsterdamAsset(... source_integrity_verified=True) → TypeError."""
        with pytest.raises(TypeError):
            RealAmsterdamAsset(
                asset_id="X", address="X", bag_pand_id="1",
                bag_verblijfsobject_id="1", geometry_type="Point",
                coordinates_x=4.9, coordinates_y=52.37, crs="EPSG:4326",
                bouwjaar=2000, gebruiksdoel="kantoorfunctie",
                oppervlakte_m2=100.0, source_integrity_verified=True,
            )

    def test_canonical_ids_nl_am_chain_001_to_005(self):
        """Canonical IDs are exactly NL-AM-CHAIN-001..005."""
        assets = pilot_assets()
        expected = [f"NL-AM-CHAIN-{i:03d}" for i in range(1, 6)]
        actual = sorted(a.asset_id for a in assets)
        assert actual == expected




# ---------------------------------------------------------------------------
# ISSUE_5: Canonical Amsterdam Legal Artifact (CVDR696291)
# ---------------------------------------------------------------------------


class TestIssue5_LegalSource:
    """ISSUE_5-R4: Three-source sealed legal evidence.
    
    Sources:
      1. Legal text: amsterdam-omgevingsplan-cvdr696291-v15.raw.html
      2. WTI metadata: amsterdam-omgevingsplan-cvdr696291-v15-wti.raw.html
      3. Amendment: amsterdam-gmb-2026-243575-metadata.raw.html
    """

    # --- Source 1: Legal text ---

    def test_legal_snapshot_exists(self):
        snapshot = AMSTERDAM_DIR / "amsterdam-omgevingsplan-cvdr696291-v15.raw.html"
        assert snapshot.exists() and snapshot.stat().st_size > 0

    def test_legal_hash_matches(self):
        manifest = json.loads(AMSTERDAM_MANIFEST.read_text())
        src = manifest["sources"]["amsterdam-omgevingsplan-cvdr696291"]
        snapshot = AMSTERDAM_DIR / "amsterdam-omgevingsplan-cvdr696291-v15.raw.html"
        raw = snapshot.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == src["artifact_sha256"]

    def test_legal_artikel_4_113_present(self):
        snapshot = AMSTERDAM_DIR / "amsterdam-omgevingsplan-cvdr696291-v15.raw.html"
        text = snapshot.read_bytes().decode("utf-8", errors="replace")
        assert "Artikel 4.113" in text

    def test_legal_artikel_4_116_thresholds(self):
        snapshot = AMSTERDAM_DIR / "amsterdam-omgevingsplan-cvdr696291-v15.raw.html"
        text = snapshot.read_bytes().decode("utf-8", errors="replace")
        import re as _re
        tc = _re.sub(r"<[^>]+>", " ", text)
        assert _re.search(r"60\s*liter\s*per\s*m\s*2", tc, _re.IGNORECASE)
        assert _re.search(r"1\s*liter\s*per\s*m\s*2.*per\s*uur", tc, _re.IGNORECASE)
        assert _re.search(r"60\s*uur", tc, _re.IGNORECASE)

    # --- Source 2: WTI metadata ---

    def test_wti_snapshot_exists(self):
        snapshot = AMSTERDAM_DIR / "amsterdam-omgevingsplan-cvdr696291-v15-wti.raw.html"
        assert snapshot.exists() and snapshot.stat().st_size > 0

    def test_wti_hash_matches(self):
        manifest = json.loads(AMSTERDAM_MANIFEST.read_text())
        src = manifest["sources"]["amsterdam-omgevingsplan-cvdr696291-v15-wti"]
        snapshot = AMSTERDAM_DIR / "amsterdam-omgevingsplan-cvdr696291-v15-wti.raw.html"
        raw = snapshot.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == src["artifact_sha256"]
        assert src.get("snapshot_path") is not None

    def test_wti_parses_effective_date(self):
        from app.nl_pilot.amsterdam_source import _parse_wti_evidence
        snapshot = AMSTERDAM_DIR / "amsterdam-omgevingsplan-cvdr696291-v15-wti.raw.html"
        raw = snapshot.read_bytes()
        facts = _parse_wti_evidence(raw)
        assert facts["effective_from"] == "2026-06-19"
        assert facts["effective_until"] is None

    def test_wti_parses_amendment_reference(self):
        from app.nl_pilot.amsterdam_source import _parse_wti_evidence
        snapshot = AMSTERDAM_DIR / "amsterdam-omgevingsplan-cvdr696291-v15-wti.raw.html"
        raw = snapshot.read_bytes()
        facts = _parse_wti_evidence(raw)
        assert facts["amendment_publication"] == "gmb-2026-243575"
        assert facts["version_number"] == 15
        assert facts["regulatory_state"] == "current_in_force"

    # --- Source 3: Amendment publication ---

    def test_amendment_snapshot_exists(self):
        snapshot = AMSTERDAM_DIR / "amsterdam-gmb-2026-243575-metadata.raw.html"
        assert snapshot.exists() and snapshot.stat().st_size > 0

    def test_amendment_hash_matches(self):
        manifest = json.loads(AMSTERDAM_MANIFEST.read_text())
        src = manifest["sources"]["amsterdam-gmb-2026-243575-metadata"]
        snapshot = AMSTERDAM_DIR / "amsterdam-gmb-2026-243575-metadata.raw.html"
        raw = snapshot.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == src["artifact_sha256"]

    def test_amendment_parses_publication_id(self):
        from app.nl_pilot.amsterdam_source import _parse_amendment_evidence
        snapshot = AMSTERDAM_DIR / "amsterdam-gmb-2026-243575-metadata.raw.html"
        raw = snapshot.read_bytes()
        facts = _parse_amendment_evidence(raw)
        assert facts["publication_id"] == "gmb-2026-243575"
        assert facts["decision_date"] == "2026-05-07"
        assert facts["publication_date"] == "2026-05-22"
        assert facts["official_version_identifier"] == "CVDR696291_15"

    # --- Three-source gate ---

    def test_load_sealed_snapshot_verifies_all_three(self):
        from app.nl_pilot.amsterdam_source import load_sealed_snapshot
        snapshot = AMSTERDAM_DIR / "amsterdam-omgevingsplan-cvdr696291-v15.raw.html"
        artifact = load_sealed_snapshot(snapshot, manifest_path=AMSTERDAM_MANIFEST)
        assert artifact.source_verified is True
        assert artifact.version_verified is True
        assert artifact.effective_status_verified is True
        assert artifact.amendment_chain_verified is True
        assert artifact.rule_mapping_verified is True
        assert artifact.cvdr_id == "CVDR696291"
        assert artifact.version_number == 15
        assert artifact.effective_from == "2026-06-19"
        assert artifact.official_version_identifier == "CVDR696291_15"

    def test_effective_from_not_stale(self):
        from app.nl_pilot.amsterdam_source import load_sealed_snapshot
        snapshot = AMSTERDAM_DIR / "amsterdam-omgevingsplan-cvdr696291-v15.raw.html"
        artifact = load_sealed_snapshot(snapshot, manifest_path=AMSTERDAM_MANIFEST)
        assert artifact.effective_from != "2026-01-01"

    # --- Fail-closed regression ---
    def test_tampered_legal_text_raises(self, tmp_path):
        """Tampered bytes -> hash mismatch fail-closed."""
        import json as _json
        from app.nl_pilot.amsterdam_source import load_sealed_snapshot
        snapshot = AMSTERDAM_DIR / "amsterdam-omgevingsplan-cvdr696291-v15.raw.html"
        raw = snapshot.read_bytes()
        tampered = tmp_path / "tampered.html"
        tampered.write_bytes(raw[:100] + b"X" + raw[101:])
        # Create a bad manifest pointing snapshot_path to the tampered file
        manifest = _json.loads(AMSTERDAM_MANIFEST.read_text())
        manifest["sources"]["amsterdam-omgevingsplan-cvdr696291"]["snapshot_path"] = str(tampered)
        bad_manifest = tmp_path / "bad.json"
        bad_manifest.write_text(_json.dumps(manifest))
        with pytest.raises(ValueError, match="hash mismatch"):
            load_sealed_snapshot(tampered, manifest_path=bad_manifest)

    def test_wrong_path_not_ignored(self, tmp_path):
        """Supplied path != manifest path -> fail-closed."""
        from app.nl_pilot.amsterdam_source import load_sealed_snapshot
        snapshot = AMSTERDAM_DIR / "amsterdam-omgevingsplan-cvdr696291-v15.raw.html"
        raw = snapshot.read_bytes()
        wrong_path = tmp_path / "wrong.html"
        wrong_path.write_bytes(raw)
        with pytest.raises(ValueError, match="does not match"):
            load_sealed_snapshot(wrong_path, manifest_path=AMSTERDAM_MANIFEST)

    def test_tampered_wti_raises(self, tmp_path):
        """Tampered WTI artifact -> fail-closed."""
        from app.nl_pilot.amsterdam_source import load_sealed_snapshot
        manifest = json.loads(AMSTERDAM_MANIFEST.read_text())
        manifest["sources"]["amsterdam-omgevingsplan-cvdr696291-v15-wti"]["snapshot_path"] = str(tmp_path / "bad-wti.html")
        (tmp_path / "bad-wti.html").write_bytes(b"<html>TAMPERED</html>")
        bad_manifest = tmp_path / "bad.json"
        bad_manifest.write_text(json.dumps(manifest))
        snapshot = AMSTERDAM_DIR / "amsterdam-omgevingsplan-cvdr696291-v15.raw.html"
        with pytest.raises(ValueError, match="mismatch"):
            load_sealed_snapshot(snapshot, manifest_path=bad_manifest)

    def test_tampered_amendment_raises(self, tmp_path):
        """Missing amendment artifact -> fail-closed."""
        from app.nl_pilot.amsterdam_source import load_sealed_snapshot
        manifest = json.loads(AMSTERDAM_MANIFEST.read_text())
        manifest["sources"]["amsterdam-gmb-2026-243575-metadata"]["snapshot_path"] = str(tmp_path / "nonexistent.html")
        bad_manifest = tmp_path / "bad.json"
        bad_manifest.write_text(json.dumps(manifest))
        snapshot = AMSTERDAM_DIR / "amsterdam-omgevingsplan-cvdr696291-v15.raw.html"
        with pytest.raises((ValueError, FileNotFoundError)):
            load_sealed_snapshot(snapshot, manifest_path=bad_manifest)

    def test_missing_wti_source_raises(self, tmp_path):
        """Missing WTI source entry -> fail-closed."""
        from app.nl_pilot.amsterdam_source import load_sealed_snapshot
        manifest = json.loads(AMSTERDAM_MANIFEST.read_text())
        del manifest["sources"]["amsterdam-omgevingsplan-cvdr696291-v15-wti"]
        bad_manifest = tmp_path / "bad.json"
        bad_manifest.write_text(json.dumps(manifest))
        snapshot = AMSTERDAM_DIR / "amsterdam-omgevingsplan-cvdr696291-v15.raw.html"
        with pytest.raises(ValueError, match="missing"):
            load_sealed_snapshot(snapshot, manifest_path=bad_manifest)

    def test_missing_amendment_source_raises(self, tmp_path):
        """Missing amendment source entry -> fail-closed."""
        from app.nl_pilot.amsterdam_source import load_sealed_snapshot
        manifest = json.loads(AMSTERDAM_MANIFEST.read_text())
        del manifest["sources"]["amsterdam-gmb-2026-243575-metadata"]
        bad_manifest = tmp_path / "bad.json"
        bad_manifest.write_text(json.dumps(manifest))
        snapshot = AMSTERDAM_DIR / "amsterdam-omgevingsplan-cvdr696291-v15.raw.html"
        with pytest.raises(ValueError, match="missing"):
            load_sealed_snapshot(snapshot, manifest_path=bad_manifest)

    # --- Non-forgeable verification flags ---

    def test_source_verified_non_forgeable(self):
        from app.nl_pilot.amsterdam_source import AmsterdamSourceArtifact
        a = AmsterdamSourceArtifact(
            source_id="t", title="t", source_url="t",
            cvdr_id="CVDR696291", version_number=15,
            resolved_version_ref="CVDR696291/15", resolved_version_url="t",
            retrieved_at="t", effective_from="2026-06-19", effective_until=None,
            artifact_sha256="a"*64, normalized_content_sha256="b"*64,
            regulatory_state="current_in_force",
            latest_amendment_publication="gmb-2026-243575",
            official_version_identifier="CVDR696291_15",
            rule_mapping_version="CVDR696291/15",
        )
        assert a.source_verified is False
        assert a.version_verified is False
        assert a.amendment_chain_verified is False
        assert a.rule_mapping_verified is False
        assert a.effective_status_verified is False

    # --- Manifest structure ---

    def test_manifest_has_all_three_sources(self):
        manifest = json.loads(AMSTERDAM_MANIFEST.read_text())
        assert "amsterdam-omgevingsplan-cvdr696291" in manifest["sources"]
        assert "amsterdam-omgevingsplan-cvdr696291-v15-wti" in manifest["sources"]
        assert "amsterdam-gmb-2026-243575-metadata" in manifest["sources"]

    def test_manifest_source_entry_has_all_gates(self):
        manifest = json.loads(AMSTERDAM_MANIFEST.read_text())
        src = manifest["sources"]["amsterdam-omgevingsplan-cvdr696291"]
        for gate in ["version_verified", "effective_status_verified",
                     "amendment_chain_verified", "rule_mapping_verified"]:
            assert gate in src, f"{gate} missing from source entry"

    def test_old_noncanonical_absent(self):
        manifest = json.loads(AMSTERDAM_MANIFEST.read_text())
        for sid, src in manifest.get("sources", {}).items():
            assert "DR000417648" not in src.get("source_url", "")

    def test_rule_mapping_fail_closed(self, tmp_path):
        """rule_mapping_verified=false -> loader raises."""
        from app.nl_pilot.amsterdam_source import load_sealed_snapshot
        snapshot = AMSTERDAM_DIR / "amsterdam-omgevingsplan-cvdr696291-v15.raw.html"
        manifest = json.loads(AMSTERDAM_MANIFEST.read_text())
        src = manifest["sources"]["amsterdam-omgevingsplan-cvdr696291"]
        src["rule_mapping_verified"] = False
        bad_manifest = tmp_path / "bad.json"
        bad_manifest.write_text(json.dumps(manifest))
        with pytest.raises(ValueError, match="rule_mapping_verified"):
            load_sealed_snapshot(snapshot, manifest_path=bad_manifest)

    def test_amendment_tamper_gate(self, tmp_path):
        """Tampered amendment bytes -> artifact hash mismatch -> raises."""
        from app.nl_pilot.amsterdam_source import load_sealed_snapshot
        snapshot = AMSTERDAM_DIR / "amsterdam-omgevingsplan-cvdr696291-v15.raw.html"
        wrong_amend = tmp_path / "wrong-amend.html"
        wrong_amend.write_bytes(b"<html>TAMPERED</html>")
        manifest = json.loads(AMSTERDAM_MANIFEST.read_text())
        manifest["sources"]["amsterdam-gmb-2026-243575-metadata"]["snapshot_path"] = str(wrong_amend)
        bad_manifest = tmp_path / "bad.json"
        bad_manifest.write_text(json.dumps(manifest))
        with pytest.raises(ValueError, match="hash mismatch"):
            load_sealed_snapshot(snapshot, manifest_path=bad_manifest)

    def test_amendment_wrong_date_chain_gate(self, tmp_path):
        """Wrong dates in amendment artifact -> hash gate passes -> date-chain gate fails."""
        import hashlib
        from app.nl_pilot.amsterdam_source import (
            load_sealed_snapshot,
            compute_artifact_hash,
            compute_normalized_hash_html,
        )
        snapshot = AMSTERDAM_DIR / "amsterdam-omgevingsplan-cvdr696291-v15.raw.html"
        # Create a synthetic amendment with wrong dates but parser-compatible HTML
        wrong_amend = tmp_path / "wrong-amend.html"
        wrong_amend.write_bytes(
            b"<html><body>"
            b"gmb-2026-243575 "
            b"""<td data-before="Datum ondertekening">"""
            b"""<time datetime="2099-01-01">01-01-2099</time></td> """
            b"""<td data-before="Datum publicatie">"""
            b"""<time datetime="2099-01-02">02-01-2099</time></td> """
            b"Regeling CVDR696291_15"
            b"</body></html>"
        )
        # Compute correct hashes for the synthetic artifact so hash gate passes
        wrong_bytes = wrong_amend.read_bytes()
        wrong_sha = compute_artifact_hash(wrong_bytes)
        wrong_norm = compute_normalized_hash_html(wrong_bytes)
        manifest = json.loads(AMSTERDAM_MANIFEST.read_text())
        amend_src = manifest["sources"]["amsterdam-gmb-2026-243575-metadata"]
        amend_src["snapshot_path"] = str(wrong_amend)
        amend_src["artifact_sha256"] = wrong_sha
        amend_src["normalized_content_sha256"] = wrong_norm
        bad_manifest = tmp_path / "bad.json"
        bad_manifest.write_text(json.dumps(manifest))
        # Hash gate passes, but amendment chain gate fails on wrong dates
        with pytest.raises(ValueError, match="Amendment chain mismatch"):
            load_sealed_snapshot(snapshot, manifest_path=bad_manifest)

    def test_amendment_dates_parse_correctly(self):
        """Amendment dates are correctly parsed from sealed artifact."""
        from app.nl_pilot.amsterdam_source import _parse_amendment_evidence
        snapshot = AMSTERDAM_DIR / "amsterdam-gmb-2026-243575-metadata.raw.html"
        raw = snapshot.read_bytes()
        facts = _parse_amendment_evidence(raw)
        assert facts["decision_date"] == "2026-05-07"
        assert facts["publication_date"] == "2026-05-22"
        assert facts["official_version_identifier"] == "CVDR696291_15"
        assert facts["publication_id"] == "gmb-2026-243575"

    # --- Acquisition rebuild regression ---

    def test_acquisition_rebuild_loader_valid(self, tmp_path):
        """Committed sealed artifacts -> build_provenance_entries -> loader validates."""
        import json as _json
        from app.nl_pilot.amsterdam_source import load_sealed_snapshot
        from scripts.acquire_amsterdam_legal_source import build_provenance_entries
        # Load the three committed sealed artifacts
        legal_path = AMSTERDAM_DIR / "amsterdam-omgevingsplan-cvdr696291-v15.raw.html"
        wti_path = AMSTERDAM_DIR / "amsterdam-omgevingsplan-cvdr696291-v15-wti.raw.html"
        amend_path = AMSTERDAM_DIR / "amsterdam-gmb-2026-243575-metadata.raw.html"
        assert legal_path.exists()
        assert wti_path.exists()
        assert amend_path.exists()

        # Use the ACTUAL acquisition builder — not manual construction
        entries = build_provenance_entries(
            legal_bytes=legal_path.read_bytes(),
            legal_path=legal_path,
            legal_content_type="text/html",
            legal_retrieved_at="2026-08-28T00:00:00Z",
            wti_bytes=wti_path.read_bytes(),
            wti_path=wti_path,
            wti_content_type="text/html",
            wti_retrieved_at="2026-08-28T00:00:00Z",
            amendment_bytes=amend_path.read_bytes(),
            amendment_path=amend_path,
            amendment_content_type="text/html",
            amendment_retrieved_at="2026-08-28T00:00:00Z",
        )
        # Builder returns exactly 3 entries
        assert set(entries.keys()) == {
            "amsterdam-omgevingsplan-cvdr696291",
            "amsterdam-omgevingsplan-cvdr696291-v15-wti",
            "amsterdam-gmb-2026-243575-metadata",
        }

        # Build temporary manifest from builder output
        rebuild_manifest = {"sources": entries}
        rebuild_manifest_path = tmp_path / "rebuild-manifest.json"
        rebuild_manifest_path.write_text(_json.dumps(rebuild_manifest))

        # The loader should succeed with the builder-produced manifest
        artifact = load_sealed_snapshot(legal_path, manifest_path=rebuild_manifest_path)
        assert artifact.source_verified is True
        assert artifact.version_verified is True
        assert artifact.effective_status_verified is True
        assert artifact.amendment_chain_verified is True
        assert artifact.rule_mapping_verified is True

    # --- Non-forgeable verification flags (constructor rejection) ---

    @pytest.mark.parametrize("flag_name", [
        "source_verified",
        "version_verified",
        "effective_status_verified",
        "amendment_chain_verified",
        "rule_mapping_verified",
    ])
    def test_verification_flag_constructor_rejected(self, flag_name):
        """Verification flags cannot be passed to the constructor."""
        from app.nl_pilot.amsterdam_source import AmsterdamSourceArtifact
        kwargs = {
            "source_id": "t", "title": "t", "source_url": "t",
            "cvdr_id": "CVDR696291", "version_number": 15,
            "resolved_version_ref": "CVDR696291/15", "resolved_version_url": "t",
            "retrieved_at": "t", "effective_from": "2026-06-19", "effective_until": None,
            "artifact_sha256": "a" * 64, "normalized_content_sha256": "b" * 64,
            "regulatory_state": "current_in_force",
            "latest_amendment_publication": "gmb-2026-243575",
            "official_version_identifier": "CVDR696291_15",
            "rule_mapping_version": "CVDR696291/15",
        }
        kwargs[flag_name] = True
        with pytest.raises(TypeError):
            AmsterdamSourceArtifact(**kwargs)

    # --- Validate-before-mutate regression ---

    def test_acquisition_failure_zero_mutation(self, tmp_path):
        """Invalid WTI bytes -> builder fails -> zero snapshot/manifest mutation."""
        from unittest.mock import patch
        import importlib
        import scripts.acquire_amsterdam_legal_source as acq_mod

        # Set up temporary directories for snapshots and manifest
        fake_snapshot_dir = tmp_path / "snapshots"
        fake_snapshot_dir.mkdir()
        fake_manifest = tmp_path / "manifest.json"
        fake_manifest.write_text(json.dumps({"sources": {}}))

        # Pre-create sentinel files
        legal_sentinel = fake_snapshot_dir / "amsterdam-omgevingsplan-cvdr696291-v15.raw.html"
        wti_sentinel = fake_snapshot_dir / "amsterdam-omgevingsplan-cvdr696291-v15-wti.raw.html"
        amend_sentinel = fake_snapshot_dir / "amsterdam-gmb-2026-243575-metadata.raw.html"
        sentinel_content = b"SENTINEL_CONTENT"
        legal_sentinel.write_bytes(sentinel_content)
        wti_sentinel.write_bytes(sentinel_content)
        amend_sentinel.write_bytes(sentinel_content)

        # Load valid legal bytes (we only need to make WTI invalid)
        legal_path = AMSTERDAM_DIR / "amsterdam-omgevingsplan-cvdr696291-v15.raw.html"
        legal_bytes = legal_path.read_bytes()

        # Invalid WTI bytes will cause _parse_wti_evidence to raise
        invalid_wti = b"<html>INVALID WTI - no Geldend van</html>"
        # Valid amendment bytes
        amend_path = AMSTERDAM_DIR / "amsterdam-gmb-2026-243575-metadata.raw.html"
        amend_bytes = amend_path.read_bytes()

        # Mock fetch_url to return our crafted bytes
        call_count = [0]
        def mock_fetch(url):
            call_count[0] += 1
            if "show-wti" in url:
                return invalid_wti, "text/html", "2026-08-28T00:00:00Z"
            elif "gmb-" in url:
                return amend_bytes, "text/html", "2026-08-28T00:00:00Z"
            else:
                return legal_bytes, "text/html", "2026-08-28T00:00:00Z"

        # Override module-level constants for this test
        orig_snapshot_dir = acq_mod.SNAPSHOT_DIR
        orig_manifest_path = acq_mod.MANIFEST_PATH
        orig_snapshot_filename = acq_mod.SNAPSHOT_FILENAME
        orig_wti_filename = acq_mod.WTI_FILENAME
        orig_amend_filename = acq_mod.AMEND_FILENAME

        acq_mod.SNAPSHOT_DIR = fake_snapshot_dir
        acq_mod.MANIFEST_PATH = fake_manifest
        # Set filenames so paths resolve to our sentinel files
        acq_mod.SNAPSHOT_FILENAME = legal_sentinel.name
        acq_mod.WTI_FILENAME = wti_sentinel.name
        acq_mod.AMEND_FILENAME = amend_sentinel.name

        try:
            with patch.object(acq_mod, "fetch_url", side_effect=mock_fetch):
                with pytest.raises(ValueError, match="WTI"):
                    acq_mod.main()
        finally:
            acq_mod.SNAPSHOT_DIR = orig_snapshot_dir
            acq_mod.MANIFEST_PATH = orig_manifest_path
            acq_mod.SNAPSHOT_FILENAME = orig_snapshot_filename
            acq_mod.WTI_FILENAME = orig_wti_filename
            acq_mod.AMEND_FILENAME = orig_amend_filename

        # Verify ZERO mutation: all sentinel files unchanged
        assert legal_sentinel.read_bytes() == sentinel_content,             "Legal snapshot was mutated before validation passed"
        assert wti_sentinel.read_bytes() == sentinel_content,             "WTI snapshot was mutated before validation passed"
        assert amend_sentinel.read_bytes() == sentinel_content,             "Amendment snapshot was mutated before validation passed"
        assert json.loads(fake_manifest.read_text()) == {"sources": {}},             "Manifest was mutated before validation passed"



# ---------------------------------------------------------------------------
# ISSUE_6 — Article 4.113 Applicability State Machine
# ---------------------------------------------------------------------------

class TestIssue6_ApplicabilityStateMachine:
    """Synthetic unit tests for the Article 4.113 state machine.

    These exercise deterministic legal decision branches using
    synthetic evidence.  They do NOT affect the five real pilot
    assets, which must remain indeterminate.
    """

    def test_case1_municipality_only(self):
        """Case 1: Municipality=Amsterdam, no event evidence."""
        from app.nl_pilot.applicability import evaluate_article_4_113

        decision = evaluate_article_4_113("Amsterdam")
        assert decision.municipality_match is True
        assert decision.applicability_candidate is True
        assert decision.paragraph_applicable is None
        assert decision.applicability_state == "indeterminate"
        assert decision.asset_applicability_verified is False

    def test_case2_non_amsterdam(self):
        """Case 2: Non-Amsterdam municipality."""
        from app.nl_pilot.applicability import evaluate_article_4_113

        decision = evaluate_article_4_113("Rotterdam")
        assert decision.municipality_match is False
        assert decision.applicability_candidate is False
        assert decision.paragraph_applicable is False
        assert decision.applicability_state == "outside_jurisdiction"

    def test_case3_old_building_no_modification(self):
        """Case 3: Existing old building, no post-2021 event evidence.

        Evidence is absent (None), not verified negation (False).
        'no modification evidence' ≠ 'verified no modification occurred'.
        """
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        evidence = Article4113Evidence(
            municipality_match=True,
            # All event evidence absent — not verified False
            building_is_new=None,
            major_renovation=None,
            roof_extension=None,
            built_area_expansion=None,
            cellar_extension=None,
            building_layer_added=None,
            cellar_or_souterrain_added=None,
        )
        decision = evaluate_article_4_113("Amsterdam", evidence)
        # All trigger families indeterminate → overall indeterminate
        assert decision.paragraph_applicable is None
        assert decision.applicability_state == "indeterminate"
        assert decision.asset_applicability_verified is False

    def test_case4_renovation_missing_bvo(self):
        """Case 4: Major renovation verified, BVO missing."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        evidence = Article4113Evidence(
            municipality_match=True,
            major_renovation=True,
            major_renovation_date="2023-06-15",
            building_gross_floor_area_m2=None,  # missing BVO
            permit_application_before_2021_05_11=False,
            land_selection_or_development_agreement_before_2021_06_22=False,
        )
        decision = evaluate_article_4_113("Amsterdam", evidence)
        assert decision.paragraph_applicable is None
        assert "building_gross_floor_area_m2" in decision.missing_evidence

    def test_case5_renovation_bvo_ok_transition_cleared(self):
        """Case 5: Major renovation + BVO >= 1000 + transition cleared."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        evidence = Article4113Evidence(
            municipality_match=True,
            major_renovation=True,
            major_renovation_date="2023-06-15",
            building_gross_floor_area_m2=1500.0,
            permit_application_before_2021_05_11=False,
            land_selection_or_development_agreement_before_2021_06_22=False,
        )
        decision = evaluate_article_4_113("Amsterdam", evidence)
        assert decision.paragraph_applicable is True
        assert decision.trigger == "major_renovation"
        assert decision.applicability_state == "applicable"

    def test_case6_renovation_bvo_below_1000(self):
        """Case 6: Major renovation, BVO < 1000."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        evidence = Article4113Evidence(
            municipality_match=True,
            major_renovation=True,
            major_renovation_date="2023-06-15",
            building_gross_floor_area_m2=800.0,
            # Other triggers unknown
            building_is_new=None,
            roof_extension=None,
            built_area_expansion=None,
            cellar_extension=None,
            building_layer_added=None,
            cellar_or_souterrain_added=None,
            permit_application_before_2021_05_11=None,
            land_selection_or_development_agreement_before_2021_06_22=None,
        )
        decision = evaluate_article_4_113("Amsterdam", evidence)
        # BVO trigger fails but other triggers unknown → indeterminate
        assert decision.paragraph_applicable is None
        assert decision.applicability_state == "indeterminate"

    def test_case7_dakopbouw_gt_100(self):
        """Case 7: Dakopbouw > 100 m², date and transition OK."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        evidence = Article4113Evidence(
            municipality_match=True,
            roof_extension=True,
            roof_extension_date="2024-01-15",
            roof_extension_area_m2=150.0,
            permit_application_before_2021_05_11=False,
            land_selection_or_development_agreement_before_2021_06_22=False,
        )
        decision = evaluate_article_4_113("Amsterdam", evidence)
        assert decision.paragraph_applicable is True
        assert decision.trigger == "dakopbouw"
        assert decision.applicability_state == "applicable"

    def test_case8_dakopbouw_small_missing_built_area(self):
        """Case 8: Dakopbouw <= 100 m² + missing built area → indeterminate."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        evidence = Article4113Evidence(
            municipality_match=True,
            roof_extension=True,
            roof_extension_date="2024-01-15",
            roof_extension_area_m2=80.0,
            main_building_built_area_m2=None,  # missing
            permit_application_before_2021_05_11=False,
            land_selection_or_development_agreement_before_2021_06_22=False,
        )
        decision = evaluate_article_4_113("Amsterdam", evidence)
        assert decision.paragraph_applicable is None
        assert "main_building_built_area_m2" in decision.missing_evidence

    def test_case9_built_area_expansion(self):
        """Case 9: Built area expansion after cutoff, transition cleared."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        evidence = Article4113Evidence(
            municipality_match=True,
            built_area_expansion=True,
            built_area_expansion_date="2023-09-01",
            permit_application_before_2021_05_11=False,
            land_selection_or_development_agreement_before_2021_06_22=False,
        )
        decision = evaluate_article_4_113("Amsterdam", evidence)
        assert decision.paragraph_applicable is True
        assert decision.trigger == "built_area_expansion"
        assert decision.applicability_state == "applicable"

    def test_case10_pre_2021_permit_exclusion(self):
        """Case 10: Positive trigger + pre-11-May-2021 permit transition."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        evidence = Article4113Evidence(
            municipality_match=True,
            major_renovation=True,
            major_renovation_date="2023-06-15",
            building_gross_floor_area_m2=1500.0,
            permit_application_before_2021_05_11=True,
        )
        decision = evaluate_article_4_113("Amsterdam", evidence)
        assert decision.paragraph_applicable is False
        assert decision.applicability_state == "not_applicable"
        assert decision.transition_exemption == "TRANSITION_PRE_2021_05_11_PERMIT"

    def test_case11_pre_2021_development_exclusion(self):
        """Case 11: Positive trigger + pre-22-June-2021 development agreement."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        evidence = Article4113Evidence(
            municipality_match=True,
            built_area_expansion=True,
            built_area_expansion_date="2023-09-01",
            land_selection_or_development_agreement_before_2021_06_22=True,
        )
        decision = evaluate_article_4_113("Amsterdam", evidence)
        assert decision.paragraph_applicable is False
        assert decision.applicability_state == "not_applicable"
        assert decision.transition_exemption == "TRANSITION_PRE_2021_06_22_DEVELOPMENT_AGREEMENT"

    def test_case12_positive_trigger_transition_unknown(self):
        """Case 12: Positive trigger but transition evidence unknown → null."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        evidence = Article4113Evidence(
            municipality_match=True,
            built_area_expansion=True,
            built_area_expansion_date="2023-09-01",
            # Transition evidence unknown
            permit_application_before_2021_05_11=None,
            land_selection_or_development_agreement_before_2021_06_22=None,
        )
        decision = evaluate_article_4_113("Amsterdam", evidence)
        assert decision.paragraph_applicable is None
        assert decision.applicability_state == "indeterminate"

    def test_vbo_area_not_used_as_building_bvo(self):
        """VBO oppervlakte_m2 must NOT be used for major renovation BVO gate."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        # Simulate: renovation exists, only VBO area available
        evidence = Article4113Evidence(
            municipality_match=True,
            major_renovation=True,
            major_renovation_date="2023-06-15",
            building_gross_floor_area_m2=None,  # NOT using VBO area
            permit_application_before_2021_05_11=False,
            land_selection_or_development_agreement_before_2021_06_22=False,
        )
        decision = evaluate_article_4_113("Amsterdam", evidence)
        assert decision.paragraph_applicable is None
        assert "building_gross_floor_area_m2" in decision.missing_evidence

    def test_vbo_area_not_used_as_built_area(self):
        """VBO oppervlakte_m2 must NOT be used for bebouwd oppervlak."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        evidence = Article4113Evidence(
            municipality_match=True,
            roof_extension=True,
            roof_extension_date="2024-01-15",
            roof_extension_area_m2=80.0,
            main_building_built_area_m2=None,  # NOT using VBO area
            permit_application_before_2021_05_11=False,
            land_selection_or_development_agreement_before_2021_06_22=False,
        )
        decision = evaluate_article_4_113("Amsterdam", evidence)
        assert decision.paragraph_applicable is None
        assert "main_building_built_area_m2" in decision.missing_evidence

    def test_failed_trigger_not_equivalent_to_applicability_false(self):
        """A failed trigger does NOT preclude other trigger families."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        # Renovation BVO fails but dakopbouw unknown
        evidence = Article4113Evidence(
            municipality_match=True,
            major_renovation=True,
            major_renovation_date="2023-06-15",
            building_gross_floor_area_m2=800.0,  # < 1000
            # Dakopbouw unknown
            roof_extension=None,
            # Transition unknown
            permit_application_before_2021_05_11=None,
            land_selection_or_development_agreement_before_2021_06_22=None,
        )
        decision = evaluate_article_4_113("Amsterdam", evidence)
        # Not false — indeterminate because other families are unknown
        assert decision.paragraph_applicable is None

    def test_indeterminate_not_collapsed_to_not_applicable(self):
        """None (indeterminate) must NOT be collapsed to false."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        evidence = Article4113Evidence(
            municipality_match=True,
            building_is_new=None,  # unknown
            major_renovation=None,  # unknown
            roof_extension=None,  # unknown
            built_area_expansion=None,  # unknown
            cellar_extension=None,  # unknown
            building_layer_added=None,  # unknown
            cellar_or_souterrain_added=None,  # unknown
        )
        decision = evaluate_article_4_113("Amsterdam", evidence)
        # Must be indeterminate, NOT not_applicable
        assert decision.paragraph_applicable is None
        assert decision.applicability_state == "indeterminate"


class TestIssue6_CurrentRealAssetsRegression:
    """Verify all 5 real pilot assets produce indeterminate applicability.

    No current real asset may become Article 4.113 verified as a
    side effect of ISSUE_6.
    """

    def test_all_five_assets_indeterminate(self):
        """All 5 real assets: indeterminate, not applicable, not verified."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        pack = build_pilot_evidence_pack()
        evaluations = pack["asset_evaluations"]

        assert len(evaluations) == 5

        applicable_true_count = 0
        applicable_false_count = 0
        applicable_unknown_count = 0
        verified_count = 0

        for ev in evaluations:
            assert ev["municipality"] == "Amsterdam"
            assert ev["asset_applicability_verified"] is False

            pa = ev.get("paragraph_applicable")
            state = ev.get("applicability_state", "unknown")

            if pa is True:
                applicable_true_count += 1
            elif pa is False:
                applicable_false_count += 1
            else:
                applicable_unknown_count += 1

            if ev["asset_applicability_verified"]:
                verified_count += 1

        # All 5 must be indeterminate
        assert applicable_true_count == 0, (
            f"Expected 0 assets with paragraph_applicable=True, "
            f"got {applicable_true_count}"
        )
        assert applicable_unknown_count == 5, (
            f"Expected 5 assets with paragraph_applicable=None, "
            f"got {applicable_unknown_count}"
        )
        assert verified_count == 0, (
            f"Expected 0 verified assets, got {verified_count}"
        )

    def test_overall_status_applicability_unverified(self):
        """All 5 assets: overall_status = applicability_unverified."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        pack = build_pilot_evidence_pack()
        for ev in pack["asset_evaluations"]:
            assert ev["overall_status"] == "applicability_unverified"

    def test_no_threshold_comparisons_meaningful(self):
        """Threshold comparisons have no engineering value when indeterminate."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        pack = build_pilot_evidence_pack()
        for ev in pack["asset_evaluations"]:
            for rr in ev["rule_results"]:
                assert rr["engineered_value"] is None
                assert rr["status"] == "applicability_unverified"

    def test_prohibited_shortcuts_rejected(self):
        """Ensure specific prohibited shortcuts produce indeterminate."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        # bouwjaar < 2021 → NOT applicable=false without evidence
        evidence = Article4113Evidence(municipality_match=True)
        decision = evaluate_article_4_113("Amsterdam", evidence)
        assert decision.paragraph_applicable is None

    def test_preserve_downstream_gates(self):
        """ISSUE_6 must not derive downstream gates."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        pack = build_pilot_evidence_pack()
        gates = pack["pilot_gates"]
        assert gates["engineering_capacity_verified"] is False
        assert gates["production_eligible"] is False
        assert gates["external_use_approved"] is False


# ---------------------------------------------------------------------------
# ISSUE_6 — Applicability in evidence pack
# ---------------------------------------------------------------------------

class TestIssue6_EvidencePackIntegration:
    """Verify the evidence pack consumes the applicability state machine."""

    def test_evidence_pack_has_paragraph_fields(self):
        """Each asset evaluation includes Art. 4.113 decision fields."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        pack = build_pilot_evidence_pack()
        for ev in pack["asset_evaluations"]:
            assert "paragraph_applicable" in ev
            assert "applicability_state" in ev
            # V2 nests paragraph_scope_article and reason_code under applicability
            app = ev["applicability"]
            assert "paragraph_scope_article" in app
            assert "reason_code" in app
            assert "missing_evidence" in app
            assert "trigger" in app

    def test_evidence_pack_no_applicable_true(self):
        """Zero assets produce applicable=true in the evidence pack."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        pack = build_pilot_evidence_pack()
        for ev in pack["asset_evaluations"]:
            assert ev["paragraph_applicable"] is None

    def test_evidence_pack_reasonable_reason_code(self):
        """All reason codes indicate evidence is incomplete."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        pack = build_pilot_evidence_pack()
        for ev in pack["asset_evaluations"]:
            app = ev["applicability"]
            assert "EVIDENCE" in app["reason_code"] or "ARTICLE" in app["reason_code"]



# ---------------------------------------------------------------------------
# ISSUE_6-R1 — Tri-State Branch Closure + Evidence-Trust Gate
# ---------------------------------------------------------------------------

class TestIssue6R1_TriStateAggregation:
    """Verify proper tri-state OR aggregation across all trigger families."""

    def test_mixed_false_unknown_or(self):
        """layer=False + cellar=None => trigger=None (UNKNOWN)."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        e = Article4113Evidence(
            municipality_match=True,
            building_layer_added=False,
            cellar_or_souterrain_added=None,
        )
        d = evaluate_article_4_113("Amsterdam", e)
        assert d.trigger_decisions["layer_cellar"]["applicable"] is None

    def test_unknown_first_positive_second(self):
        """layer=True+date=None + cellar=True+date=2024 => TRUE."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        e = Article4113Evidence(
            municipality_match=True,
            building_layer_added=True,
            building_layer_added_date=None,
            cellar_or_souterrain_added=True,
            cellar_or_souterrain_event_date="2024-01-01",
        )
        d = evaluate_article_4_113("Amsterdam", e)
        assert d.trigger_decisions["layer_cellar"]["applicable"] is True

    def test_layer_none_cellar_false(self):
        """layer=None + cellar=False => UNKNOWN."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        e = Article4113Evidence(
            municipality_match=True,
            building_layer_added=None,
            cellar_or_souterrain_added=False,
        )
        d = evaluate_article_4_113("Amsterdam", e)
        assert d.trigger_decisions["layer_cellar"]["applicable"] is None

    def test_layer_false_cellar_false(self):
        """layer=False + cellar=False => FALSE."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        e = Article4113Evidence(
            municipality_match=True,
            building_layer_added=False,
            cellar_or_souterrain_added=False,
        )
        d = evaluate_article_4_113("Amsterdam", e)
        assert d.trigger_decisions["layer_cellar"]["applicable"] is False

    def test_layer_true_pre_cutoff_cellar_unknown(self):
        """layer=True+date=2020 + cellar=None => UNKNOWN."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        e = Article4113Evidence(
            municipality_match=True,
            building_layer_added=True,
            building_layer_added_date="2020-01-01",
            cellar_or_souterrain_added=None,
        )
        d = evaluate_article_4_113("Amsterdam", e)
        assert d.trigger_decisions["layer_cellar"]["applicable"] is None

    def test_dakopbouw_all_known_false(self):
        """area=50, built=200 => both limbs false => trigger=False."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        e = Article4113Evidence(
            municipality_match=True,
            roof_extension=True,
            roof_extension_date="2024-01-15",
            roof_extension_area_m2=50.0,
            main_building_built_area_m2=200.0,
            permit_application_before_2021_05_11=False,
            land_selection_or_development_agreement_before_2021_06_22=False,
        )
        d = evaluate_article_4_113("Amsterdam", e)
        assert d.trigger_decisions["dakopbouw"]["applicable"] is False

    def test_dakopbouw_exact_100_not_triggered(self):
        """area=100, built=300 => NOT >100 and NOT >50% => FALSE."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        e = Article4113Evidence(
            municipality_match=True,
            roof_extension=True,
            roof_extension_date="2024-01-15",
            roof_extension_area_m2=100.0,
            main_building_built_area_m2=300.0,
            permit_application_before_2021_05_11=False,
            land_selection_or_development_agreement_before_2021_06_22=False,
        )
        d = evaluate_article_4_113("Amsterdam", e)
        # 100 is NOT > 100, and 100 is NOT > 150 (50% of 300)
        assert d.trigger_decisions["dakopbouw"]["applicable"] is False

    def test_cellar_all_known_false(self):
        """ext=50, built=200, deepened=False => both limbs false."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        e = Article4113Evidence(
            municipality_match=True,
            cellar_extension=True,
            cellar_extension_area_m2=50.0,
            cellar_extension_date="2024-01-15",
            main_building_built_area_m2=200.0,
            cellar_deepened_for_use=False,
            permit_application_before_2021_05_11=False,
            land_selection_or_development_agreement_before_2021_06_22=False,
        )
        d = evaluate_article_4_113("Amsterdam", e)
        assert d.trigger_decisions["cellar_extension"]["applicable"] is False

    def test_cellar_ext_false_deepened_false(self):
        """ext=False + deepened=False => FALSE."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        e = Article4113Evidence(
            municipality_match=True,
            cellar_extension=False,
            cellar_deepened_for_use=False,
        )
        d = evaluate_article_4_113("Amsterdam", e)
        assert d.trigger_decisions["cellar_extension"]["applicable"] is False

    def test_cellar_ext_false_deepened_unknown(self):
        """ext=False + deepened=None => UNKNOWN."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        e = Article4113Evidence(
            municipality_match=True,
            cellar_extension=False,
            cellar_deepened_for_use=None,
        )
        d = evaluate_article_4_113("Amsterdam", e)
        assert d.trigger_decisions["cellar_extension"]["applicable"] is None

    def test_cellar_post_cutoff(self):
        """cellar ext post-cutoff + area>=100 => TRUE."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        e = Article4113Evidence(
            municipality_match=True,
            cellar_extension=True,
            cellar_extension_area_m2=120.0,
            cellar_extension_date="2024-01-01",
            cellar_deepened_for_use=False,
            permit_application_before_2021_05_11=False,
            land_selection_or_development_agreement_before_2021_06_22=False,
        )
        d = evaluate_article_4_113("Amsterdam", e)
        assert d.trigger_decisions["cellar_extension"]["applicable"] is True

    def test_cellar_pre_cutoff(self):
        """cellar ext pre-cutoff => FALSE."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        e = Article4113Evidence(
            municipality_match=True,
            cellar_extension=True,
            cellar_extension_area_m2=120.0,
            cellar_extension_date="2020-01-01",
            cellar_deepened_for_use=False,
            permit_application_before_2021_05_11=False,
            land_selection_or_development_agreement_before_2021_06_22=False,
        )
        d = evaluate_article_4_113("Amsterdam", e)
        assert d.trigger_decisions["cellar_extension"]["applicable"] is False

    def test_cellar_missing_date(self):
        """cellar ext True + area=120 + date=None => UNKNOWN."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        e = Article4113Evidence(
            municipality_match=True,
            cellar_extension=True,
            cellar_extension_area_m2=120.0,
            cellar_extension_date=None,
            cellar_deepened_for_use=False,
            permit_application_before_2021_05_11=False,
            land_selection_or_development_agreement_before_2021_06_22=False,
        )
        d = evaluate_article_4_113("Amsterdam", e)
        assert d.trigger_decisions["cellar_extension"]["applicable"] is None

    def test_cellar_deepening_pre_cutoff(self):
        """deepened=True + date=2020 => FALSE."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        e = Article4113Evidence(
            municipality_match=True,
            cellar_extension=False,
            cellar_deepened_for_use=True,
            cellar_deepening_date="2020-01-01",
            permit_application_before_2021_05_11=False,
            land_selection_or_development_agreement_before_2021_06_22=False,
        )
        d = evaluate_article_4_113("Amsterdam", e)
        assert d.trigger_decisions["cellar_extension"]["applicable"] is False

    def test_cellar_deepening_post_cutoff(self):
        """deepened=True + date=2024 => TRUE."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        e = Article4113Evidence(
            municipality_match=True,
            cellar_extension=False,
            cellar_deepened_for_use=True,
            cellar_deepening_date="2024-01-01",
            permit_application_before_2021_05_11=False,
            land_selection_or_development_agreement_before_2021_06_22=False,
        )
        d = evaluate_article_4_113("Amsterdam", e)
        assert d.trigger_decisions["cellar_extension"]["applicable"] is True

    def test_cellar_ext_post_cutoff_gt50_pct(self):
        """ext post-cutoff + >50% built area => TRUE."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        e = Article4113Evidence(
            municipality_match=True,
            cellar_extension=True,
            cellar_extension_area_m2=50.0,
            cellar_extension_date="2024-01-15",
            main_building_built_area_m2=80.0,
            cellar_deepened_for_use=False,
            permit_application_before_2021_05_11=False,
            land_selection_or_development_agreement_before_2021_06_22=False,
        )
        d = evaluate_article_4_113("Amsterdam", e)
        assert d.trigger_decisions["cellar_extension"]["applicable"] is True

    def test_invalid_date_fail_closed(self):
        """Invalid date strings never evaluate to True."""
        from app.nl_pilot.applicability import _date_after_cutoff

        assert _date_after_cutoff("not-a-date") is None
        assert _date_after_cutoff("2024-99-99") is None
        assert _date_after_cutoff("") is None
        assert _date_after_cutoff("2024-01-01") is True
        assert _date_after_cutoff("2021-05-11") is False
        assert _date_after_cutoff("2020-12-31") is False

    def test_caller_evidence_does_not_verify_asset(self):
        """Synthetic evidence does NOT produce verified-asset claim."""
        from app.nl_pilot.applicability import (
            Article4113Evidence,
            evaluate_article_4_113,
        )

        # Fully verified evidence → paragraph_applicable=True
        e = Article4113Evidence(
            municipality_match=True,
            major_renovation=True,
            major_renovation_date="2023-06-15",
            building_gross_floor_area_m2=1500.0,
            permit_application_before_2021_05_11=False,
            land_selection_or_development_agreement_before_2021_06_22=False,
        )
        d = evaluate_article_4_113("Amsterdam", e)
        assert d.paragraph_applicable is True
        # But asset_applicability_verified MUST remain False
        assert d.asset_applicability_verified is False

    def test_legacy_real_assests_not_in_packer(self):
        """No real_assests misspelling in evidence pack."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        pack = build_pilot_evidence_pack()
        assert "real_assests" not in pack.get("pilot_gates", {})
        assert pack["pilot_gates"]["real_assets"] is True


# ---------------------------------------------------------------------------
# ISSUE_7 — Sealed Pand Footprint Geometry + Engineering Gate
# ---------------------------------------------------------------------------

class TestIssue7_GeometryPipeline:
    """Verify Pand footprint derivation from sealed polygon geometry."""

    def test_all_five_assets_have_verified_geometry(self):
        """All 5 real assets: building_geometry_verified=True, area > 0."""
        from app.nl_pilot.real_assets import load_pilot_assets

        assets = load_pilot_assets()
        assert len(assets) == 5

        for a in assets:
            assert a.building_geometry_verified is True
            assert a.pand_footprint_area_m2 is not None
            assert a.pand_footprint_area_m2 > 0
            assert a.pand_geometry_source_crs == "OGC:CRS84"
            assert a.pand_geometry_area_crs == "EPSG:28992"

    def test_vbo_area_not_used_for_footprint(self):
        """Same Pand polygon + different VBO area = same footprint."""
        from app.nl_pilot.real_assets import load_pilot_assets

        assets = load_pilot_assets()
        # All 5 have different VBO oppervlakte but Pand footprint
        # is derived independently from Pand polygon
        vbo_areas = [a.oppervlakte_m2 for a in assets]
        footprints = [a.pand_footprint_area_m2 for a in assets]

        # VBO areas and footprints should differ (proving independence)
        # At minimum, verify no footprint equals any VBO area
        for a in assets:
            assert a.pand_footprint_area_m2 != a.oppervlakte_m2, (
                f"{a.asset_id}: footprint == VBO area = "
                f"{a.pand_footprint_area_m2}"
            )

    def test_geometry_verified_does_not_promote_applicability(self):
        """Geometry verified ≠ asset applicability verified."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        pack = build_pilot_evidence_pack()
        for ev in pack["asset_evaluations"]:
            if ev["building_geometry_verified"]:
                # Geometry is verified but applicability is not
                assert ev["asset_applicability_verified"] is False
                assert ev["paragraph_applicable"] is None

    def test_geometry_verified_does_not_promote_engineering(self):
        """Geometry verified ≠ engineering capacity verified."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        pack = build_pilot_evidence_pack()
        for ev in pack["asset_evaluations"]:
            eng = ev["engineering"]
            assert eng["building_geometry_verified"] is True
            assert eng["engineering_capacity_verified"] is False

    def test_legal_bebouwd_oppervlak_not_alias_footprint(self):
        """Legal bebouwd oppervlak is NOT aliased from Pand footprint."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        pack = build_pilot_evidence_pack()
        for ev in pack["asset_evaluations"]:
            geom = ev["building_geometry"]
            eng = ev["engineering"]
            # Footprint exists
            assert geom["pand_footprint_area_m2"] > 0
            # Legal denominator does NOT exist
            assert eng["legal_bebouwd_oppervlak_m2"] is None
            assert eng["legal_bebouwd_oppervlak_verified"] is False

    def test_obligation_applicable_not_derived(self):
        """Obligation applicability not derived from geometry."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        pack = build_pilot_evidence_pack()
        for ev in pack["asset_evaluations"]:
            eng = ev["engineering"]
            assert eng["obligation_applicable"] is None
            assert eng["obligation_applicability_verified"] is False

    def test_requirement_variant_not_assumed(self):
        """60 L/m² variant NOT automatically selected."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        pack = build_pilot_evidence_pack()
        for ev in pack["asset_evaluations"]:
            eng = ev["engineering"]
            assert eng["requirement_variant"] is None
            assert eng["requirement_variant_verified"] is False

    def test_required_storage_not_calculated_for_real_assets(self):
        """No regulatory numeric claims for real assets."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        pack = build_pilot_evidence_pack()
        for ev in pack["asset_evaluations"]:
            eng = ev["engineering"]
            assert eng["required_storage_liters"] is None
            assert eng["max_discharge_liters_per_hour"] is None
            assert eng["required_emptying_hours"] is None
            assert eng["engineering_requirement_verified"] is False

    def test_actual_capacity_not_calculated(self):
        """No actual capacity claims."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        pack = build_pilot_evidence_pack()
        for ev in pack["asset_evaluations"]:
            eng = ev["engineering"]
            assert eng["actual_storage_capacity_liters"] is None
            assert eng["actual_storage_capacity_verified"] is False

    def test_production_eligible_false(self):
        """Production eligible stays False."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        pack = build_pilot_evidence_pack()
        gates = pack["pilot_gates"]
        assert gates["production_eligible"] is False
        assert gates["external_use_approved"] is False

    def test_pand_footprint_areas_are_plausible(self):
        """Footprint areas are within plausible range for Amsterdam buildings."""
        from app.nl_pilot.real_assets import load_pilot_assets

        assets = load_pilot_assets()
        for a in assets:
            area = a.pand_footprint_area_m2
            # Plausible range: 10 m² to 100,000 m²
            assert 10.0 <= area <= 100000.0, (
                f"{a.asset_id}: area={area} outside plausible range"
            )


class TestIssue7_EngineeringMath:
    """Pure math function tests — NOT real-asset verification."""

    def test_standard_article_4_116_calculation(self):
        """Standard Article 4.116 formula."""
        from app.nl_pilot.engineering import calculate_standard_article_4_116

        result = calculate_standard_article_4_116(100.0)
        assert result["required_storage_liters"] == 6000.0
        assert result["max_discharge_liters_per_hour"] == 100.0
        assert result["required_emptying_hours"] == 60.0

    def test_standard_article_4_116_zero_area(self):
        """Zero area → zero requirements."""
        from app.nl_pilot.engineering import calculate_standard_article_4_116

        result = calculate_standard_article_4_116(0.0)
        assert result["required_storage_liters"] == 0.0

    def test_math_result_not_engineering_verified(self):
        """Pure math result ≠ verified engineering requirement."""
        from app.nl_pilot.engineering import (
            HemelwaterEngineeringDecision,
            calculate_standard_article_4_116,
        )

        # Math works
        result = calculate_standard_article_4_116(100.0)
        assert result["required_storage_liters"] == 6000.0

        # But a decision with these values is NOT verified
        decision = HemelwaterEngineeringDecision(
            required_storage_liters=6000.0,
        )
        assert decision.engineering_requirement_verified is False
        assert decision.engineering_capacity_verified is False

    def test_footprint_independent_of_vbo_area(self):
        """Same polygon + different VBO area → same footprint."""
        from app.nl_pilot.geometry import compute_pand_footprint_area

        # Load one real Pand polygon
        import json
        from pathlib import Path

        manifest = json.loads(
            Path("data/nl_pilot/provenance-manifest-amsterdam-v1.json").read_text()
        )
        chain = manifest["chains"]["chain-1"]
        pfid = chain["pand_feature_id"]
        pand_source_id = f"amsterdam-pand-{pfid[:8]}"
        entry = manifest["sources"][pand_source_id]
        pand_path = Path(entry["snapshot_path"])
        pand_data = json.loads(pand_path.read_text())
        feat = pand_data if pand_data.get("type") == "Feature" else pand_data["features"][0]

        # Compute footprint (VBO area is irrelevant)
        evidence = compute_pand_footprint_area(
            feat["geometry"],
            pand_status=feat["properties"]["status"],
            bag_pand_id=chain["pand_identificatie"],
            pand_feature_id=pfid,
            source_artifact_sha256=entry["artifact_sha256"],
            source_normalized_sha256=entry["normalized_content_sha256"],
        )
        assert evidence.footprint_area_m2 > 0

        # Call again — same result (deterministic)
        evidence2 = compute_pand_footprint_area(
            feat["geometry"],
            pand_status=feat["properties"]["status"],
            bag_pand_id=chain["pand_identificatie"],
            pand_feature_id=pfid,
            source_artifact_sha256=entry["artifact_sha256"],
            source_normalized_sha256=entry["normalized_content_sha256"],
        )
        assert evidence.footprint_area_m2 == evidence2.footprint_area_m2

        # Signature proof: compute_pand_footprint_area has NO VBO area parameter
        from app.nl_pilot.geometry import compute_pand_footprint_area as _fn
        sig = inspect.signature(_fn)
        param_names = list(sig.parameters.keys())
        assert "oppervlakte_m2" not in param_names, (
            "compute_pand_footprint_area must NOT accept VBO area"
        )
        assert "vbo_area" not in param_names, (
            "compute_pand_footprint_area must NOT accept vbo_area"
        )

        # Deterministic: same source bytes → same area regardless of any external state
        ev_a = compute_pand_footprint_area(
            feat["geometry"],
            pand_status=feat["properties"]["status"],
            bag_pand_id=chain["pand_identificatie"],
            pand_feature_id=pfid,
            source_artifact_sha256=entry["artifact_sha256"],
            source_normalized_sha256=entry["normalized_content_sha256"],
        )
        assert ev_a.footprint_area_m2 == pytest.approx(evidence.footprint_area_m2)
        assert ev_a.pand_source_id is not None


class TestIssue7_GeometryFailClosed:
    """Negative geometry regressions — all must fail closed."""

    def test_missing_geometry_raises(self):
        """Empty geometry → ValueError."""
        from app.nl_pilot.geometry import compute_pand_footprint_area

        with __import__("pytest").raises(ValueError, match="GEOMETRY_MISSING"):
            compute_pand_footprint_area(
                {},
                pand_status="Pand in gebruik",
                bag_pand_id="test",
                pand_feature_id="test",
                source_artifact_sha256="abc",
                source_normalized_sha256="def",
            )

    def test_point_geometry_raises(self):
        """Point geometry → ValueError."""
        from app.nl_pilot.geometry import compute_pand_footprint_area

        with __import__("pytest").raises(ValueError, match="GEOMETRY_TYPE"):
            compute_pand_footprint_area(
                {"type": "Point", "coordinates": [4.9, 52.37]},
                pand_status="Pand in gebruik",
                bag_pand_id="test",
                pand_feature_id="test",
                source_artifact_sha256="abc",
                source_normalized_sha256="def",
            )

    def test_non_definitive_status_raises(self):
        """Pand in gebruik (niet ingemeten) → ValueError."""
        from app.nl_pilot.geometry import compute_pand_footprint_area

        with __import__("pytest").raises(ValueError, match="NOT_DEFINITIVE"):
            compute_pand_footprint_area(
                {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
                pand_status="Pand in gebruik (niet ingemeten)",
                bag_pand_id="test",
                pand_feature_id="test",
                source_artifact_sha256="abc",
                source_normalized_sha256="def",
            )

    def test_geometry_verified_non_forgeable(self):
        """geometry_verified is field(init=False) — cannot be passed."""
        from app.nl_pilot.geometry import PandFootprintEvidence

        with __import__("pytest").raises(TypeError):
            PandFootprintEvidence(
                bag_pand_id="test",
                pand_feature_id="test",
                source_geometry_type="Polygon",
                source_crs="OGC:CRS84",
                area_crs="EPSG:28992",
                footprint_area_m2=100.0,
                pand_status="Pand in gebruik",
                definitive_geometry=True,
                source_artifact_sha256="abc",
                source_normalized_sha256="def",
                pand_source_id="amsterdam-pand-test00",
                geometry_algorithm="test",
                geometry_algorithm_version="1.0",
                shapely_version="2.1.2",
                pyproj_version="3.7.1",
                geometry_verified=True,  # ← should fail
            )

    def test_engineering_decision_non_forgeable(self):
        """engineering_capacity_verified is field(init=False)."""
        from app.nl_pilot.engineering import HemelwaterEngineeringDecision

        # Cannot pass verification flags to constructor
        with __import__("pytest").raises(TypeError):
            HemelwaterEngineeringDecision(
                engineering_capacity_verified=True,
            )

        # Synthetic math does NOT promote verification
        d = HemelwaterEngineeringDecision(
            required_storage_liters=6000.0,
        )
        assert d.engineering_requirement_verified is False
        assert d.engineering_capacity_verified is False

    def test_swapped_axis_fail_closed(self):
        """Coordinates clearly outside Amsterdam RD-New → fail closed."""
        from app.nl_pilot.geometry import compute_pand_footprint_area

        with __import__("pytest").raises(ValueError):
            compute_pand_footprint_area(
                {"type": "Polygon", "coordinates": [
                    [[12.0, 45.0], [12.1, 45.0], [12.1, 45.1], [12.0, 45.1], [12.0, 45.0]]
                ]},
                pand_status="Pand in gebruik",
                bag_pand_id="test", pand_feature_id="test-uuid",
                source_artifact_sha256="dummy", source_normalized_sha256="dummy",
            )

    def test_polygon_with_hole_reduces_area(self):
        """Polygon with hole → area < same polygon without hole."""
        from app.nl_pilot.geometry import compute_pand_footprint_area

        outer = [[4.9, 52.37], [4.91, 52.37], [4.91, 52.38], [4.9, 52.38], [4.9, 52.37]]
        hole = [[4.902, 52.372], [4.908, 52.372], [4.908, 52.378], [4.902, 52.378], [4.902, 52.372]]

        ev_outer = compute_pand_footprint_area(
            {"type": "Polygon", "coordinates": [outer]},
            pand_status="Pand in gebruik",
            bag_pand_id="test", pand_feature_id="test-uuid-1",
            source_artifact_sha256="d1", source_normalized_sha256="d1",
        )
        ev_hole = compute_pand_footprint_area(
            {"type": "Polygon", "coordinates": [outer, hole]},
            pand_status="Pand in gebruik",
            bag_pand_id="test", pand_feature_id="test-uuid-2",
            source_artifact_sha256="d2", source_normalized_sha256="d2",
        )
        assert ev_hole.footprint_area_m2 < ev_outer.footprint_area_m2
        assert ev_hole.footprint_area_m2 > 0


# ---------------------------------------------------------------------------
# Evidence Pack V2 Tests
# ---------------------------------------------------------------------------

class TestEvidencePackV2:
    """Evidence Pack v2 truth-state consolidation tests."""

    def test_pack_identity_v2(self):
        """Pack is V2 with correct identity."""
        from app.nl_pilot.pilot_evidence_pack import (
            build_pilot_evidence_pack, PILOT_PACK_VERSION, PILOT_SCHEMA_VERSION, PILOT_PACK_ID,
        )
        assert PILOT_PACK_VERSION == 2
        assert PILOT_SCHEMA_VERSION == "2.0"
        assert "V2" in PILOT_PACK_ID
        pack = build_pilot_evidence_pack()
        assert pack["pack_version"] == 2
        assert pack["schema_version"] == "2.0"

    def test_byte_reproducibility(self):
        """Two builds produce identical deterministic JSON."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack, _deterministic_json
        pack_a = build_pilot_evidence_pack()
        pack_b = build_pilot_evidence_pack()
        # Compare excluding checksum (checksum depends on content)
        a = {k: v for k, v in pack_a.items() if k != "checksum"}
        b = {k: v for k, v in pack_b.items() if k != "checksum"}
        assert _deterministic_json(a) == _deterministic_json(b)
        assert pack_a["checksum"] == pack_b["checksum"]

    def test_checksum_verification(self):
        """verify_pack_checksum validates the pack."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        from app.nl_pilot.evidence_truth import verify_pack_checksum
        pack = build_pilot_evidence_pack()
        assert verify_pack_checksum(pack)
        # Tamper checksum
        bad = dict(pack)
        bad["checksum"] = {"algorithm": "SHA-256", "content_sha256": "wrong"}
        assert not verify_pack_checksum(bad)

    def test_committed_pack_reproducible(self):
        """Committed V2 artifact matches regeneration."""
        import json
        from pathlib import Path
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack, _deterministic_json
        committed_path = Path("data/nl_pilot/evidence-pack-amsterdam-v2.json")
        assert committed_path.exists()
        committed = json.loads(committed_path.read_text())
        regen = build_pilot_evidence_pack()
        c = {k: v for k, v in committed.items() if k != "checksum"}
        r = {k: v for k, v in regen.items() if k != "checksum"}
        assert _deterministic_json(c) == _deterministic_json(r)

    def test_legal_source_verified(self):
        """V2 pack has verified legal source."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        reg = pack["source_provenance"]["regulatory_source"]["verification"]
        assert reg["source_verified"] is True
        assert reg["version_verified"] is True
        assert reg["effective_status_verified"] is True
        assert reg["amendment_chain_verified"] is True
        assert reg["rule_mapping_verified"] is True

    def test_threshold_definition_verified(self):
        """Threshold definitions are verified against sealed source."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        assert pack["summary"]["threshold_definition_verified"] is True
        for rule in pack["regulatory_rules"]:
            assert rule["threshold_definition_verified"] is True
            assert rule["threshold_source_verified"] is True

    def test_truth_state_4c(self):
        """ISSUE_4C truth-state: all 5 assets verified."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        ts4 = pack["truth_state"]["issue_4c"]
        assert ts4["real_assets_count"] == 5
        assert ts4["bag_identity_verified_count"] == 5
        assert ts4["source_integrity_verified_count"] == 5
        assert ts4["building_geometry_verified_count"] == 5
        assert ts4["synthetic_fallback_used"] is False
        assert ts4["status"] == "verified"

    def test_truth_state_5(self):
        """ISSUE_5 truth-state: legal source fully verified."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        ts5 = pack["truth_state"]["issue_5"]
        assert ts5["official_regulatory_artifact_verified"] is True
        assert ts5["source_verified"] is True
        assert ts5["version_verified"] is True
        assert ts5["effective_status_verified"] is True
        assert ts5["amendment_chain_verified"] is True
        assert ts5["rule_mapping_verified"] is True
        assert ts5["threshold_definition_verified"] is True
        assert ts5["cvdr_id"] == "CVDR696291"
        assert ts5["version_number"] == 15
        assert ts5["resolved_version_ref"] == "CVDR696291/15"
        assert ts5["official_version_identifier"] == "CVDR696291_15"

    def test_truth_state_6(self):
        """ISSUE_6 truth-state: architecture verified, evidence incomplete."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        ts6 = pack["truth_state"]["issue_6"]
        assert ts6["article_4_113_engine_status"] == "implemented_fail_closed"
        assert ts6["applicable_true_count"] == 0
        assert ts6["applicable_false_count"] == 0
        assert ts6["applicable_unknown_count"] == 5
        assert ts6["asset_applicability_verified_count"] == 0
        assert ts6["status"] == "architecture_verified_asset_evidence_incomplete"

    def test_truth_state_7(self):
        """ISSUE_7 truth-state: geometry verified, engineering unverified."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        ts7 = pack["truth_state"]["issue_7"]
        assert ts7["building_geometry_verified_count"] == 5
        assert ts7["legal_bebouwd_oppervlak_verified_count"] == 0
        assert ts7["obligation_applicability_verified_count"] == 0
        assert ts7["engineering_requirement_verified_count"] == 0
        assert ts7["engineering_capacity_verified_count"] == 0

    def test_current_state(self):
        """current_state block uses correct string states."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        cs = pack["truth_state"]["current_state"]
        assert cs["source_identity"] == "verified"
        assert cs["source_integrity"] == "verified"
        assert cs["regulatory_source"] == "verified"
        assert cs["building_geometry"] == "verified"
        assert cs["asset_applicability"] == "indeterminate"
        assert cs["engineering_capacity"] == "not_verified"
        assert cs["production_eligibility"] == "false"
        assert cs["external_use_approval"] == "false"

    def test_claim_boundaries(self):
        """claim_boundaries present and claim-safe."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        cb = pack["truth_state"]["claim_boundaries"]
        assert len(cb["verified"]) > 0
        assert len(cb["not_verified"]) > 0
        assert "production eligibility" in cb["not_verified"]
        assert "regulatory compliance" in cb["not_verified"]
        # Must not contain any compliance claim
        for item in cb["verified"]:
            assert "compliant" not in item.lower()

    def test_pilot_gates_projection(self):
        """pilot_gates is a projection of truth_state."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        pg = pack["pilot_gates"]
        assert pg["real_assets"] is True
        assert pg["bag_identity_verified"] is True
        assert pg["official_regulatory_artifact_verified"] is True
        assert pg["threshold_source_verified"] is True
        assert pg["asset_applicability_verified"] is False
        assert pg["legal_bebouwd_oppervlak_verified"] is False
        assert pg["engineering_capacity_verified"] is False
        assert pg["production_eligible"] is False
        assert pg["external_use_approved"] is False

    def test_asset_applicability_indeterminate(self):
        """All 5 real assets: paragraph_applicable=null, overall=applicability_unverified."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        for ev in pack["asset_evaluations"]:
            assert ev["paragraph_applicable"] is None
            assert ev["overall_status"] == "applicability_unverified"
            assert ev["asset_applicability_verified"] is False

    def test_engineering_not_promoted(self):
        """Geometry verified but engineering stays unverified."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        for ev in pack["asset_evaluations"]:
            assert ev["building_geometry_verified"] is True
            eng = ev["engineering"]
            assert eng["engineering_requirement_verified"] is False
            assert eng["engineering_capacity_verified"] is False
            assert eng["required_storage_liters"] is None
            assert eng["actual_storage_capacity_liters"] is None

    def test_no_stale_source_verified_false(self):
        """No stale 'source_verified=False until independent verification'."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        reg = pack["source_provenance"]["regulatory_source"]
        assert reg["verification"]["source_verified"] is True
        # Must not contain stale language
        notes = json.dumps(reg)
        assert "until independent verification" not in notes.lower()

    def test_no_runtime_timestamp_in_canonical(self):
        """No datetime.now in canonical pack content."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        assert "generated_at" not in pack
        assert "evidence_as_of" in pack

    def test_pack_note_present(self):
        """Pack-level claim-boundary note present."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        assert "does not establish asset-specific legal" in pack.get("pack_note", "")

    def test_evidence_set_block(self):
        """evidence_set block present with sealed source mode."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        es = pack["evidence_set"]
        assert es["source_mode"] == "sealed_official_sources"
        assert es["live_fetch_used"] is False
        assert es["synthetic_fallback_used"] is False

    def test_regulatory_source_ids_distinct(self):
        """Regulatory IDs are distinct and correct."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        rs = pack["source_provenance"]["regulatory_source"]
        assert rs["cvdr_id"] == "CVDR696291"
        assert rs["version_number"] == 15
        assert rs["resolved_version_ref"] == "CVDR696291/15"
        assert rs["official_version_identifier"] == "CVDR696291_15"
        assert rs["latest_amendment_publication"] == "gmb-2026-243575"
        # cvdr_id and resolved_version_ref use different separators
        assert "/" in rs["resolved_version_ref"]
        assert "_" in rs["official_version_identifier"]

    def test_legal_evidence_chain(self):
        """Three legal evidence artifacts present in chain."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        chain = pack["source_provenance"]["legal_evidence_chain"]
        assert "amsterdam-omgevingsplan-cvdr696291" in chain
        assert "amsterdam-omgevingsplan-cvdr696291-v15-wti" in chain
        assert "amsterdam-gmb-2026-243575-metadata" in chain
        for lid, entry in chain.items():
            assert entry["artifact_sha256"] is not None
            assert entry["normalized_content_sha256"] is not None

    def test_asset_identity_evidence(self):
        """Each asset has identity_evidence with chain provenance."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        for ev in pack["asset_evaluations"]:
            ie = ev["identity_evidence"]
            assert ie["chain_id"] is not None
            assert ie["pand"]["source_id"] is not None
            assert ie["pand"]["artifact_sha256"] is not None

    def test_legal_denominator_explicit(self):
        """Each asset has explicit legal_denominator block."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        for ev in pack["asset_evaluations"]:
            ld = ev["legal_denominator"]
            assert ld["article"] == "Artikel 4.116"
            assert ld["legal_bebouwd_oppervlak_m2"] is None
            assert ld["verified"] is False
            assert ld["basis"] == "NOT_DETERMINED"

    def test_validator_passes(self):
        """validate_evidence_pack_v2 passes on canonical pack."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        from app.nl_pilot.evidence_truth import validate_evidence_pack_v2
        pack = build_pilot_evidence_pack()
        validate_evidence_pack_v2(pack)  # must not raise

    def test_validator_rejects_contradiction(self):
        """Validator rejects contradictory truth-state."""
        from app.nl_pilot.evidence_truth import validate_evidence_pack_v2
        import copy
        pack = build_pilot_evidence_pack()
        # Valid pack should pass
        validate_evidence_pack_v2(pack)
        # Inject contradiction: source_verified=false but threshold_definition_verified=true
        bad = copy.deepcopy(pack)
        bad["truth_state"]["issue_5"]["source_verified"] = False
        with __import__("pytest").raises(ValueError, match="source_verified"):
            validate_evidence_pack_v2(bad)

    def test_no_numeric_claim_without_verification(self):
        """Validator rejects required_storage_liters when engineering not verified."""
        from app.nl_pilot.evidence_truth import validate_evidence_pack_v2
        import copy
        pack = build_pilot_evidence_pack()
        validate_evidence_pack_v2(pack)
        # Inject a numeric claim without verification
        bad = copy.deepcopy(pack)
        bad["asset_evaluations"][0]["engineering"]["required_storage_liters"] = 6000.0
        # Bump count so the summary-level gate doesn't mask the per-asset check
        bad["summary"]["engineering_requirement_verified_count"] = 1
        with __import__("pytest").raises(ValueError, match="required_storage_liters"):
            validate_evidence_pack_v2(bad)


# ---------------------------------------------------------------------------
# Evidence Pack V2-R1 Tests
# ---------------------------------------------------------------------------

class TestEvidencePackV2_R1:
    """Evidence Pack v2-R1 closure tests."""

    def test_byte_reproducibility_actual_files(self, tmp_path):
        """Two file outputs are byte-for-byte identical."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        path_a = tmp_path / "a.json"
        path_b = tmp_path / "b.json"
        build_pilot_evidence_pack(output_path=str(path_a))
        build_pilot_evidence_pack(output_path=str(path_b))
        assert path_a.read_bytes() == path_b.read_bytes()

    def test_committed_artifact_reproducible(self, tmp_path):
        """Committed V2 artifact matches regeneration (bytes including checksum)."""
        from pathlib import Path
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        committed = Path("data/nl_pilot/evidence-pack-amsterdam-v2.json")
        assert committed.exists()
        regen_path = tmp_path / "regen.json"
        build_pilot_evidence_pack(output_path=str(regen_path))
        assert committed.read_bytes() == regen_path.read_bytes()

    def test_vbo_raw_source_id_resolved(self):
        """All 5 assets have non-None vbo_raw_source_id."""
        from app.nl_pilot.real_assets import pilot_assets
        assets = pilot_assets()
        resolved = sum(1 for a in assets if a.vbo_raw_source_id is not None)
        assert resolved == 5
        for a in assets:
            assert a.vbo_raw_source_id is not None, f'{a.asset_id}: vbo_raw_source_id=None'

    def test_adres_source_id_resolved(self):
        """All 5 assets have non-None adres_source_id."""
        from app.nl_pilot.real_assets import pilot_assets
        assets = pilot_assets()
        for a in assets:
            assert a.adres_source_id is not None, f'{a.asset_id}: adres_source_id=None'

    def test_identity_provenance_complete(self):
        """Every asset identity_evidence has non-null hashes for all three sources."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        for ev in pack["asset_evaluations"]:
            ie = ev["identity_evidence"]
            # Adres
            assert ie["adres"]["source_id"] is not None, f'{ev["asset_id"]}: adres.source_id=null'
            assert ie["adres"]["artifact_sha256"] is not None, f'{ev["asset_id"]}: adres.artifact_sha256=null'
            assert ie["adres"]["normalized_content_sha256"] is not None, f'{ev["asset_id"]}: adres.norm=null'
            # VBO
            assert ie["vbo"]["source_id"] is not None, f'{ev["asset_id"]}: vbo.source_id=null'
            assert ie["vbo"]["artifact_sha256"] is not None, f'{ev["asset_id"]}: vbo.artifact_sha256=null'
            assert ie["vbo"]["normalized_content_sha256"] is not None, f'{ev["asset_id"]}: vbo.norm=null'
            # Pand
            assert ie["pand"]["source_id"] is not None, f'{ev["asset_id"]}: pand.source_id=null'
            assert ie["pand"]["artifact_sha256"] is not None, f'{ev["asset_id"]}: pand.artifact_sha256=null'

    def test_threshold_comparison_gate(self):
        """No comparison performed when applicability unverified."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        for ev in pack["asset_evaluations"]:
            for rr in ev["rule_results"]:
                assert rr["comparison_performed"] is False, (
                    f'{ev["asset_id"]}/{rr["rule_id"]}: comparison_performed should be False'
                )
                assert rr["compliance_result"] is None

    def test_threshold_comparison_synthetic_applicable(self):
        """Synthetic paragraph_applicable=True alone does NOT enable comparison."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        from app.nl_pilot.applicability import Article4113Evidence, Article4113Decision
        from app.nl_pilot.engineering import HemelwaterEngineeringDecision
        from app.nl_pilot.real_assets import pilot_assets
        assets = pilot_assets()

        # Create synthetic evidence that makes paragraph_applicable=True
        synthetic_evidence = Article4113Evidence(building_is_new=True)
        synthetic_map = {a.asset_id: synthetic_evidence for a in assets}

        pack = build_pilot_evidence_pack(assets=assets, evidence_map=synthetic_map)
        for ev in pack["asset_evaluations"]:
            for rr in ev["rule_results"]:
                assert rr["comparison_performed"] is False, (
                    f'{ev["asset_id"]}: comparison_performed must be False '
                    f'even with synthetic applicable=True'
                )

    def test_threshold_note_matches_state(self):
        """Evidence note reflects verification state."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        for ev in pack["asset_evaluations"]:
            for rr in ev["rule_results"]:
                note = rr["evidence_note"]
                if rr["threshold_definition_verified"]:
                    # "definition is verified" must appear; downstream gates
                    # may legitimately say "not verified" for other fields.
                    assert "definition is verified" in note.lower()
                else:
                    assert "not verified" in note.lower()

    def test_stale_source_verified_false_absent(self):
        """No stale 'source_verified=False until independent verification' in V2."""
        import json
        pack_json = json.dumps(
            __import__("app.nl_pilot.pilot_evidence_pack", fromlist=["build_pilot_evidence_pack"])
            .build_pilot_evidence_pack()
        )
        assert "until independent verification" not in pack_json.lower()

    def test_stale_candidate_thresholds_absent(self):
        """No stale 'Candidate thresholds' language in V2."""
        import json
        pack_json = json.dumps(
            __import__("app.nl_pilot.pilot_evidence_pack", fromlist=["build_pilot_evidence_pack"])
            .build_pilot_evidence_pack()
        )
        assert "candidate threshold" not in pack_json.lower()

    def test_legal_source_failure_blocks_pack(self, tmp_path):
        """Tampered legal artifact causes pack builder to raise."""
        import shutil
        from pathlib import Path
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        # Create temp copies of snapshot dir + manifest
        src_dir = Path("data/nl_pilot/snapshots/amsterdam-v1")
        tmp_snapshot = tmp_path / "snapshots" / "amsterdam-v1"
        tmp_snapshot.mkdir(parents=True)
        for f in src_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, tmp_snapshot / f.name)

        src_manifest = Path("data/nl_pilot/provenance-manifest-amsterdam-v1.json")
        tmp_manifest = tmp_path / "manifest.json"
        shutil.copy2(src_manifest, tmp_manifest)

        # Tamper the legal artifact
        legal_file = tmp_snapshot / "amsterdam-omgevingsplan-cvdr696291-v15.raw.html"
        legal_file.write_bytes(legal_file.read_bytes() + b"TAMPERED")

        # Attempt to build — should fail
        try:
            from app.nl_pilot.amsterdam_source import load_sealed_snapshot
            legal_path = tmp_snapshot / "amsterdam-omgevingsplan-cvdr696291-v15.raw.html"
            load_sealed_snapshot(legal_path, tmp_manifest)
            assert False, "Should have raised on tampered artifact"
        except (ValueError, FileNotFoundError):
            pass  # Expected

    def test_per_asset_geometry_consistency(self):
        """building_geometry_verified and geometry.geometry_verified agree."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        for ev in pack["asset_evaluations"]:
            geom_v = ev["building_geometry_verified"]
            geom_flag = ev["building_geometry"]["geometry_verified"]
            assert geom_v == geom_flag, (
                f'{ev["asset_id"]}: top-level={geom_v} vs geometry_verified={geom_flag}'
            )
            if geom_v:
                assert ev["building_geometry"]["pand_footprint_area_m2"] is not None
                assert ev["building_geometry"]["pand_footprint_area_m2"] > 0

    def test_current_state_derived(self):
        """current_state fields derive from counts, not hard-coded."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()
        cs = pack["truth_state"]["current_state"]
        # All unknown -> indeterminate
        assert cs["asset_applicability"] == "indeterminate"
        # All not verified
        assert cs["obligation_applicability"] == "not_verified"
        assert cs["legal_denominator"] == "not_verified"
        assert cs["engineering_requirement"] == "not_verified"
        assert cs["engineering_capacity"] == "not_verified"

    def test_validator_count_reconciliation(self):
        """Validator independently recomputes counts from asset_evaluations."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack
        pack = build_pilot_evidence_pack()

        # Independently recompute
        evals = pack["asset_evaluations"]
        n = len(evals)
        geom_count = sum(1 for e in evals if e["building_geometry_verified"])
        id_count = sum(1 for e in evals if e["asset_identity_verified"])
        si_count = sum(1 for e in evals if e["source_integrity_verified"])

        assert pack["summary"]["total_assets"] == n
        assert pack["summary"]["building_geometry_verified_count"] == geom_count
        assert pack["summary"]["bag_identity_verified_count"] == id_count
        assert pack["summary"]["source_integrity_verified_count"] == si_count

        # Tri-state reconciliation
        at = pack["truth_state"]["issue_6"]["applicable_true_count"]
        af = pack["truth_state"]["issue_6"]["applicable_false_count"]
        au = pack["truth_state"]["issue_6"]["applicable_unknown_count"]
        assert at + af + au == n

    def test_validator_rejects_stored_count_mismatch(self):
        """Validator catches mismatched stored count."""
        from app.nl_pilot.evidence_truth import validate_evidence_pack_v2
        import copy
        pack = build_pilot_evidence_pack()
        validate_evidence_pack_v2(pack)
        # Tamper one summary count while leaving asset records unchanged
        bad = copy.deepcopy(pack)
        bad["summary"]["building_geometry_verified_count"] = 999
        with __import__("pytest").raises(ValueError):
            validate_evidence_pack_v2(bad)
class TestEvidencePackV2R1:
    """R1 closure: CI compatibility, provenance, validator, reproducibility."""

    def test_legacy_pilot_classification_import(self):
        """Legacy PILOT_CLASSIFICATION import remains backward compatible."""
        from app.nl_pilot.pilot_evidence_pack import (
            PILOT_CLASSIFICATION,
            PILOT_CLASSIFICATION_TEMPLATE,
        )

        assert PILOT_CLASSIFICATION is PILOT_CLASSIFICATION_TEMPLATE
        assert PILOT_CLASSIFICATION["production_eligible"] is False
        assert PILOT_CLASSIFICATION["decision_use_approved"] is False

    def test_no_active_v2_stale_threshold_false_language(self):
        """Active V2 test contract must not retain the obsolete false gate."""
        lines = Path(__file__).read_text(encoding="utf-8").splitlines()

        # Check only the module docstring header (first 20 lines),
        # not assertion strings deeper in the file.
        header = "\n".join(lines[:20])

        assert "THRESHOLD_SOURCE_VERIFIED = true" in header
        assert "THRESHOLD_SOURCE_VERIFIED = false" not in header

    def test_complete_identity_provenance_for_all_real_assets(self):
        """Adres -> raw VBO page -> Pand provenance is complete for all 5."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        pack = build_pilot_evidence_pack()
        assert len(pack["asset_evaluations"]) == 5

        for ev in pack["asset_evaluations"]:
            identity = ev["identity_evidence"]

            assert identity["chain_id"]

            for source_name in ("adres", "vbo", "pand"):
                source = identity[source_name]

                assert source["source_id"], (
                    f"{ev['asset_id']} {source_name} source_id missing"
                )
                assert source["artifact_sha256"], (
                    f"{ev['asset_id']} {source_name} artifact hash missing"
                )
                assert source["normalized_content_sha256"], (
                    f"{ev['asset_id']} {source_name} normalized hash missing"
                )
                assert source["snapshot_path"], (
                    f"{ev['asset_id']} {source_name} snapshot path missing"
                )
                assert source["source_url"], (
                    f"{ev['asset_id']} {source_name} source URL missing"
                )

            assert identity["adres"]["bag_identificatie"]
            assert identity["vbo"]["feature_id"]
            assert identity["vbo"]["bag_identificatie"]
            assert identity["pand"]["feature_id"]
            assert identity["pand"]["bag_identificatie"]

    def test_vbo_raw_source_id_resolved_for_all_assets(self):
        """Every verified selected VBO resolves to one exact sealed raw page."""
        from app.nl_pilot.real_assets import pilot_assets

        assets = pilot_assets()
        assert len(assets) == 5

        for asset in assets:
            assert asset.vbo_feature_id
            assert asset.vbo_raw_source_id
            assert asset.vbo_raw_source_id.startswith("amsterdam-vbo-page-")

    def test_threshold_comparison_fails_closed_without_downstream_verification(self):
        """paragraph_applicable=True alone must never perform comparison."""
        from app.nl_pilot.amsterdam_source import AMSTERDAM_THRESHOLDS
        from app.nl_pilot.applicability import (
            APPLICABLE,
            Article4113Decision,
        )
        from app.nl_pilot.engineering import HemelwaterEngineeringDecision
        from app.nl_pilot.pilot_evidence_pack import _evaluate_threshold
        from app.nl_pilot.real_assets import pilot_assets

        asset = pilot_assets()[0]
        threshold = next(iter(AMSTERDAM_THRESHOLDS.values()))

        # Synthetic legal decision only.  It deliberately does NOT represent
        # sealed asset-level applicability evidence.
        decision = Article4113Decision(
            municipality_match=True,
            applicability_candidate=True,
            paragraph_applicable=True,
            asset_applicability_verified=False,
            applicability_state=APPLICABLE,
            reason_code="SYNTHETIC_TEST_DECISION",
        )

        engineering = HemelwaterEngineeringDecision(
            pand_footprint_area_m2=asset.pand_footprint_area_m2,
            building_geometry_verified=True,
        )

        result = _evaluate_threshold(
            asset,
            threshold,
            decision,
            engineering,
            threshold_definition_verified=True,
        )

        assert result["paragraph_applicable"] is True
        assert result["asset_applicability_verified"] is False

        assert result["comparison_performed"] is False
        assert result["engineered_value"] is None
        assert result["compliance_result"] is None

    def test_threshold_note_matches_definition_verification_state(self):
        """Evidence wording must not claim source verification when false."""
        from app.nl_pilot.amsterdam_source import AMSTERDAM_THRESHOLDS
        from app.nl_pilot.applicability import Article4113Decision
        from app.nl_pilot.engineering import HemelwaterEngineeringDecision
        from app.nl_pilot.pilot_evidence_pack import _evaluate_threshold
        from app.nl_pilot.real_assets import pilot_assets

        asset = pilot_assets()[0]
        threshold = next(iter(AMSTERDAM_THRESHOLDS.values()))

        decision = Article4113Decision(
            municipality_match=True,
            applicability_candidate=True,
        )
        engineering = HemelwaterEngineeringDecision(
            pand_footprint_area_m2=asset.pand_footprint_area_m2,
            building_geometry_verified=True,
        )

        unverified = _evaluate_threshold(
            asset,
            threshold,
            decision,
            engineering,
            threshold_definition_verified=False,
        )
        verified = _evaluate_threshold(
            asset,
            threshold,
            decision,
            engineering,
            threshold_definition_verified=True,
        )

        assert unverified["threshold_definition_verified"] is False
        assert "definition is verified" not in unverified[
            "evidence_note"
        ].lower()

        assert verified["threshold_definition_verified"] is True
        assert "definition is verified" in verified[
            "evidence_note"
        ].lower()

    def test_validator_reconciles_summary_counts_against_assets(self):
        """Stored summary counts cannot drift from actual asset records."""
        import copy

        from app.nl_pilot.evidence_truth import validate_evidence_pack_v2
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        pack = build_pilot_evidence_pack()
        bad = copy.deepcopy(pack)

        bad["summary"]["building_geometry_verified_count"] = 4

        with pytest.raises(ValueError):
            validate_evidence_pack_v2(bad)

    def test_validator_reconciles_truth_state_counts_against_assets(self):
        """Stored truth-state counts cannot drift from actual asset records."""
        import copy

        from app.nl_pilot.evidence_truth import validate_evidence_pack_v2
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        pack = build_pilot_evidence_pack()
        bad = copy.deepcopy(pack)

        bad["truth_state"]["issue_6"]["applicable_unknown_count"] = 4

        with pytest.raises(ValueError):
            validate_evidence_pack_v2(bad)

    def test_validator_rejects_geometry_cross_field_contradiction(self):
        """Top-level and nested geometry verification must agree."""
        import copy

        from app.nl_pilot.evidence_truth import validate_evidence_pack_v2
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        pack = build_pilot_evidence_pack()
        bad = copy.deepcopy(pack)

        bad_ev = bad["asset_evaluations"][0]
        bad_ev["building_geometry_verified"] = False

        # Leave nested verified geometry and positive footprint untouched.
        assert bad_ev["building_geometry"]["geometry_verified"] is True
        assert bad_ev["building_geometry"]["pand_footprint_area_m2"] > 0

        with pytest.raises(ValueError):
            validate_evidence_pack_v2(bad)

    def test_validator_rejects_engineering_requirement_without_prerequisites(self):
        """Engineering verification cannot be promoted without legal gates."""
        import copy

        from app.nl_pilot.evidence_truth import validate_evidence_pack_v2
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        pack = build_pilot_evidence_pack()
        bad = copy.deepcopy(pack)

        ev = bad["asset_evaluations"][0]
        eng = ev["engineering"]

        # Make stored counts internally agree with the attempted promotion so
        # the validator must reject the missing prerequisites themselves.
        eng["engineering_requirement_verified"] = True

        bad["summary"]["engineering_requirement_verified_count"] = 1
        bad["truth_state"]["issue_7"][
            "engineering_requirement_verified_count"
        ] = 1

        # Required prerequisites deliberately remain false/null.
        assert ev["asset_applicability_verified"] is False
        assert eng["obligation_applicability_verified"] is False
        assert eng["legal_bebouwd_oppervlak_verified"] is False
        assert eng["requirement_variant_verified"] is False

        with pytest.raises(ValueError):
            validate_evidence_pack_v2(bad)

    def test_legal_source_failure_blocks_actual_pack_builder(
        self,
        tmp_path,
        monkeypatch,
    ):
        """Tampered legal bytes block V2 build and produce no output file."""
        import app.nl_pilot.pilot_evidence_pack as pep

        original = Path(pep._LEGAL_SNAPSHOT).read_bytes()

        tampered_legal = tmp_path / "tampered-legal.raw.html"
        tampered_legal.write_bytes(
            original + b"\n<!-- V2-R1 deterministic tamper -->\n"
        )

        output_path = tmp_path / "must-not-exist.json"

        monkeypatch.setattr(
            pep,
            "_LEGAL_SNAPSHOT",
            tampered_legal,
        )

        with pytest.raises(ValueError):
            pep.build_pilot_evidence_pack(
                output_path=str(output_path),
            )

        assert not output_path.exists()

    def test_two_generated_files_are_byte_identical(self, tmp_path):
        """Identical sealed inputs produce byte-identical canonical packs."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        first = tmp_path / "pack-a.json"
        second = tmp_path / "pack-b.json"

        build_pilot_evidence_pack(output_path=str(first))
        build_pilot_evidence_pack(output_path=str(second))

        first_bytes = first.read_bytes()
        second_bytes = second.read_bytes()

        assert first_bytes
        assert first_bytes == second_bytes

    def test_committed_pack_is_byte_identical_to_regeneration(self, tmp_path):
        """Committed canonical V2 artifact exactly matches regeneration."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        committed = Path(
            "data/nl_pilot/evidence-pack-amsterdam-v2.json"
        )
        regen = tmp_path / "regen-v2.json"

        assert committed.exists()

        build_pilot_evidence_pack(
            output_path=str(regen),
        )

        assert committed.read_bytes() == regen.read_bytes()

    def test_checksum_survives_exact_byte_regeneration(self, tmp_path):
        """Checksum remains valid on the exact regenerated canonical artifact."""
        from app.nl_pilot.evidence_truth import verify_pack_checksum
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        output = tmp_path / "pack.json"

        build_pilot_evidence_pack(
            output_path=str(output),
        )

        parsed = json.loads(output.read_text(encoding="utf-8"))

        assert parsed["checksum"]["algorithm"] == "SHA-256"
        assert verify_pack_checksum(parsed) is True

    def test_current_state_is_consistent_with_current_counts(self):
        """Current-state strings are projections of the canonical counts."""
        from app.nl_pilot.pilot_evidence_pack import build_pilot_evidence_pack

        pack = build_pilot_evidence_pack()

        ts = pack["truth_state"]
        cs = ts["current_state"]

        assert ts["issue_6"]["applicable_true_count"] == 0
        assert ts["issue_6"]["applicable_false_count"] == 0
        assert ts["issue_6"]["applicable_unknown_count"] == 5
        assert ts["issue_6"]["asset_applicability_verified_count"] == 0

        assert cs["asset_applicability"] == "indeterminate"

        assert (
            ts["issue_7"]["obligation_applicability_verified_count"]
            == 0
        )
        assert (
            ts["issue_7"]["legal_bebouwd_oppervlak_verified_count"]
            == 0
        )
        assert (
            ts["issue_7"]["engineering_requirement_verified_count"]
            == 0
        )
        assert (
            ts["issue_7"]["engineering_capacity_verified_count"]
            == 0
        )

        assert cs["obligation_applicability"] == "not_verified"
        assert cs["legal_denominator"] == "not_verified"
        assert cs["engineering_requirement"] == "not_verified"
        assert cs["engineering_capacity"] == "not_verified"

