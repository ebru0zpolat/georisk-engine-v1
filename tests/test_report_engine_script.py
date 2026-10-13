"""Tests for scripts/report_engine.py template rendering."""

from pathlib import Path

from scripts.report_engine import (
    merge_methodology_annex_for_pdf,
    render_cimsa_afyon_report,
    write_report,
)


def test_render_cimsa_afyon_report_substitution(tmp_path: Path) -> None:
    tpl = tmp_path / "t.md"
    tpl.write_text("x {{celsius}} y {{img_id}} z", encoding="utf-8")
    out = render_cimsa_afyon_report(
        celsius=35.5,
        img_id="LC08_TEST",
        template_path=tpl,
        append_methodology_footer=False,
    )
    assert out == "x 35.50 y LC08_TEST z"


def test_render_missing_values(tmp_path: Path) -> None:
    tpl = tmp_path / "t.md"
    tpl.write_text("{{celsius}} / {{img_id}} / {{no2_mean_mol_m2}}", encoding="utf-8")
    out = render_cimsa_afyon_report(
        celsius=None, img_id=None, template_path=tpl, append_methodology_footer=False
    )
    assert "ölçüm yok" in out and "(yok)" in out


def test_render_no2_placeholder(tmp_path: Path) -> None:
    tpl = tmp_path / "t.md"
    tpl.write_text("NO2={{no2_mean_mol_m2}}", encoding="utf-8")
    out = render_cimsa_afyon_report(
        celsius=None,
        img_id=None,
        no2_mean_mol_m2=0.00014,
        template_path=tpl,
        append_methodology_footer=False,
    )
    assert out == "NO2=0.000140"


def test_default_report_appends_methodology_footer() -> None:
    from scripts.report_engine import _TEMPLATE, render_cimsa_afyon_report

    body = render_cimsa_afyon_report(
        celsius=10.0,
        img_id="LC_TEST",
        no2_mean_mol_m2=0.0001,
        template_path=_TEMPLATE,
        append_methodology_footer=True,
    )
    assert "Otomatik eklenen feragat" in body
    assert "cco-audit-methodology.md" in body


def test_merge_methodology_annex_for_pdf(tmp_path: Path) -> None:
    meth = tmp_path / "cco-audit-methodology.md"
    meth.write_text("# Annex title\n\nAnnex **body**.", encoding="utf-8")
    out = merge_methodology_annex_for_pdf("Main line.\n", meth)
    assert out is not None
    assert "Main line." in out
    assert "\\newpage" in out
    assert "## Ek 1: Metodoloji" in out
    assert "# Annex title" in out


def test_merge_methodology_annex_for_pdf_missing_returns_none(tmp_path: Path) -> None:
    missing = tmp_path / "nope.md"
    assert merge_methodology_annex_for_pdf("x", missing) is None


def test_write_report(tmp_path: Path) -> None:
    tpl = tmp_path / "t.md"
    tpl.write_text("T={{celsius}}", encoding="utf-8")
    dest = tmp_path / "out" / "r.md"
    write_report(
        dest,
        celsius=1.0,
        img_id="id",
        template_path=tpl,
        append_methodology_footer=False,
        write_pdf=False,
    )
    assert dest.read_text(encoding="utf-8") == "T=1.00"
