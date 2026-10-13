"""Committed docs example: operational template + industrial verification appendix."""

from scripts.generate_docs_operational_risk_bundle_example import (
    compose_cimsa_operational_plus_risk_bundle_markdown,
)


def test_compose_bundle_includes_operational_and_section_e() -> None:
    text = compose_cimsa_operational_plus_risk_bundle_markdown()
    assert "Çimsa Afyon Çimento Fabrikası" in text
    assert "35.20" in text
    assert "LC08_L2SP_MOCK_EXAMPLE" in text
    assert "Otomatik eklenen feragat" in text
    assert "## E. GeoRisk API" in text
    assert "## Industrial verification" in text
    assert "aaaaaaaa-bbbb-4ccc-dddd-eeeeeeeeeeee" in text
    assert "cement_operational_audit" in text
