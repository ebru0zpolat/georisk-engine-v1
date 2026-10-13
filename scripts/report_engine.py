"""Fill operational verification report template from satellite audit outputs.

Supports placeholders ``{{celsius}}``, ``{{img_id}}``, ``{{no2_mean_mol_m2}}``.
By default appends ``docs/turkiye/snippets/report_automatic_footer_disclaimer_tr.md``
(CCO/methodology-aligned disclaimer). Does not call Earth Engine.

After writing Markdown, optionally emits a sibling ``.pdf`` via **pandoc** + LaTeX.

PDF polish (operational / boutique positioning):

- Every page header: *GeoRisk Engine - Operasyonel Şeffaflık Raporu* (see
  ``docs/turkiye/pandoc_operational_report_header.tex``).
- Appendix: full text of ``docs/turkiye/cco-audit-methodology.md`` after a page break,
  under heading **Ek 1: Metodoloji** (Markdown body is unchanged on disk; annex is merged
  only for the PDF pipeline).

**Mac:** ``brew install pandoc`` plus either BasicTeX (``brew install basictex``; adds
``/Library/TeX/texbin`` to PATH for ``xelatex``/``pdflatex``) or **`tectonic`**
(``brew install tectonic``) as a standalone PDF engine—no full TeX distribution.

Auto engine order: ``tectonic``, ``xelatex``, ``pdflatex``, ``lualatex`` (first found wins).
Override with ``REPORT_ENGINE_PDF_ENGINE=tectonic`` (or another executable name on PATH).

Manual example::

    pandoc reports/output/akcansa_canakkale_20260501.md \\
      -o reports/output/akcansa_canakkale_report.pdf --pdf-engine=tectonic

Set ``REPORT_ENGINE_SKIP_PDF=true`` to skip PDF generation without changing callers.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_MAC_TEXBIN = Path("/Library/TeX/texbin")
_CCO_METHODOLOGY_MD = _REPO_ROOT / "docs" / "turkiye" / "cco-audit-methodology.md"
_PANDOC_HEADER_TEX = (
    _REPO_ROOT / "docs" / "turkiye" / "pandoc_operational_report_header.tex"
)

_logger = logging.getLogger(__name__)
_TEMPLATE = (
    _REPO_ROOT
    / "docs"
    / "turkiye"
    / "templates"
    / "cimsa_afyon_operational_verification_report.md"
)
_METHODLOGY_FOOTER = (
    _REPO_ROOT
    / "docs"
    / "turkiye"
    / "snippets"
    / "report_automatic_footer_disclaimer_tr.md"
)


def merge_methodology_annex_for_pdf(
    main_body: str,
    methodology_path: Path,
) -> str | None:
    """Append **Ek 1: Metodoloji** (full ``methodology_path``) for pandoc PDF input.

    Returns ``None`` if ``methodology_path`` is missing (caller logs / falls back).
    """
    if not methodology_path.is_file():
        return None
    annex = methodology_path.read_text(encoding="utf-8").strip()
    return (
        main_body.rstrip()
        + "\n\n\\newpage\n\n## Ek 1: Metodoloji\n\n"
        + annex
        + "\n"
    )


def _preferred_pdf_engine() -> str | None:
    override = os.getenv("REPORT_ENGINE_PDF_ENGINE", "").strip()
    if override:
        if shutil.which(override):
            return override
        _logger.warning(
            "REPORT_ENGINE_PDF_ENGINE=%r not on PATH; trying default engine search",
            override,
        )
    for exe in ("tectonic", "xelatex", "pdflatex", "lualatex"):
        if shutil.which(exe):
            return exe
    return None


def convert_to_pdf(
    md_path: Path,
    pdf_path: Path,
    *,
    css_file_path: Path | None = None,
) -> None:
    """Render Markdown to PDF using pandoc + LaTeX (see module docstring for header / Ek 1).

    ``css_file_path`` is ignored: LaTeX PDF output does not use the HTML/CSS stylesheet.
    """
    _ = css_file_path

    pandoc_bin = shutil.which("pandoc")
    if not pandoc_bin:
        _logger.warning(
            "PDF export skipped: pandoc not found. Mac: brew install pandoc basictex",
        )
        return

    md_abs = md_path.resolve()
    pdf_abs = pdf_path.resolve()
    pdf_abs.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    path = env.get("PATH", "")
    if _MAC_TEXBIN.is_dir() and str(_MAC_TEXBIN) not in path.split(os.pathsep):
        env["PATH"] = str(_MAC_TEXBIN) + os.pathsep + path

    main_text = md_abs.read_text(encoding="utf-8")
    bundled = merge_methodology_annex_for_pdf(main_text, _CCO_METHODOLOGY_MD)
    tmp_md: Path | None = None
    if bundled is None:
        _logger.warning(
            "PDF Ek 1 omitted — methodology file missing: %s",
            _CCO_METHODOLOGY_MD,
        )
        pandoc_src = md_abs
    else:
        fd, tmp_name = tempfile.mkstemp(suffix=".md", prefix="georisk_pdf_", text=True)
        os.close(fd)
        tmp_md = Path(tmp_name)
        tmp_md.write_text(bundled, encoding="utf-8")
        pandoc_src = tmp_md

    cmd = [
        pandoc_bin,
        str(pandoc_src),
        "-o",
        str(pdf_abs),
        "--from",
        "markdown",
        "--resource-path",
        str(md_abs.parent),
    ]
    if _PANDOC_HEADER_TEX.is_file():
        cmd.extend(["--include-in-header", str(_PANDOC_HEADER_TEX)])
    engine = _preferred_pdf_engine()
    if engine:
        cmd.extend(["--pdf-engine", engine])

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        _logger.warning(
            "PDF export failed for %s (pandoc exit %s): %s",
            md_abs,
            exc.returncode,
            detail or exc,
        )
    except OSError as exc:
        _logger.warning("PDF export failed for %s: %s", md_abs.resolve(), exc)
    finally:
        if tmp_md is not None:
            tmp_md.unlink(missing_ok=True)


def methodology_footer_markdown() -> str:
    """Return canonical CCO/methodology disclaimer appendix (Turkish Markdown)."""
    return _METHODLOGY_FOOTER.read_text(encoding="utf-8").strip()


def render_cimsa_afyon_report(
    *,
    celsius: float | None,
    img_id: str | None,
    no2_mean_mol_m2: float | None = None,
    template_path: Path | None = None,
    append_methodology_footer: bool = True,
) -> str:
    """Substitute template placeholders for thermal ID, °C, and optional NO₂ mean."""
    path = template_path or _TEMPLATE
    body = path.read_text(encoding="utf-8")
    c_str = f"{celsius:.2f}" if celsius is not None else "— (ölçüm yok)"
    i_str = img_id if img_id else "— (yok)"
    if no2_mean_mol_m2 is not None:
        n_str = f"{float(no2_mean_mol_m2):.6f}"
    else:
        n_str = "— (ölçüm yok)"
    core = (
        body.replace("{{celsius}}", c_str)
        .replace("{{img_id}}", i_str)
        .replace("{{no2_mean_mol_m2}}", n_str)
    )
    if not append_methodology_footer:
        return core
    footer = methodology_footer_markdown()
    return f"{core.rstrip()}\n\n---\n\n{footer}\n"


def write_report(
    output_path: Path,
    *,
    celsius: float | None,
    img_id: str | None,
    no2_mean_mol_m2: float | None = None,
    template_path: Path | None = None,
    append_methodology_footer: bool = True,
    write_pdf: bool = True,
) -> Path:
    text = render_cimsa_afyon_report(
        celsius=celsius,
        img_id=img_id,
        no2_mean_mol_m2=no2_mean_mol_m2,
        template_path=template_path,
        append_methodology_footer=append_methodology_footer,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    skip_pdf = os.getenv("REPORT_ENGINE_SKIP_PDF", "").lower() in {
        "1",
        "true",
        "yes",
    }
    if write_pdf and not skip_pdf:
        convert_to_pdf(output_path, output_path.with_suffix(".pdf"))
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render Çimsa Afyon operational verification Markdown from metrics.",
    )
    parser.add_argument(
        "--celsius",
        type=float,
        default=None,
        help="Observed max surface temperature (°C).",
    )
    parser.add_argument(
        "--img-id",
        dest="img_id",
        default=None,
        help="Landsat scene / system:index identifier.",
    )
    parser.add_argument(
        "--no2-mean-mol-m2",
        dest="no2_mean_mol_m2",
        type=float,
        default=None,
        help="Mean tropospheric NO₂ column (mol/m²) over AOI.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=_REPO_ROOT / "reports" / "output" / "cimsa_afyon_operational_verification.md",
        help="Output Markdown path.",
    )
    parser.add_argument(
        "--no-methodology-footer",
        action="store_true",
        help="Do not append docs/turkiye/snippets/report_automatic_footer_disclaimer_tr.md",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Do not write a sibling PDF next to the Markdown output.",
    )
    args = parser.parse_args()
    out = write_report(
        args.output,
        celsius=args.celsius,
        img_id=args.img_id,
        no2_mean_mol_m2=args.no2_mean_mol_m2,
        append_methodology_footer=not args.no_methodology_footer,
        write_pdf=not args.no_pdf,
    )
    print(out.resolve())


if __name__ == "__main__":
    main()
