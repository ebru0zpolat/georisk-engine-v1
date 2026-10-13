from io import BytesIO
import textwrap

from jinja2 import Environment, FileSystemLoader

from app.schemas.risk import RiskScoreResponse


env = Environment(loader=FileSystemLoader("app/reports/templates"))


def build_pdf_report(result: RiskScoreResponse, insights: list) -> bytes:
    try:
        from weasyprint import HTML
    except ImportError as e:
        return _build_simple_pdf_report(result, insights)
    except OSError as e:
        return _build_simple_pdf_report(result, insights)

    template = env.get_template("risk_report.html")
    ctx = result.model_dump()
    ctx["insights"] = [i.model_dump() for i in insights]
    html = template.render(**ctx)

    try:
        return HTML(string=html).write_pdf()
    except OSError:
        return _build_simple_pdf_report(result, insights)


def _build_simple_pdf_report(result: RiskScoreResponse, insights: list) -> bytes:
    import pydyf

    lines = [
        "GeoRisk Engine Report",
        "",
        f"Asset: {result.asset_name}",
        f"Sector: {result.sector}",
        f"Location: {result.latitude}, {result.longitude}",
        f"Radius: {result.radius_km} km",
        "",
        f"Overall Risk: {result.overall_score}/100 ({result.risk_band})",
        f"Data mode: {result.data_mode}"
        + ("" if result.production_eligible else " (not production-eligible)"),
        "",
        "Component Scores",
        f"Industrial: {result.components.industrial}",
        f"Pollution: {result.components.pollution}",
        f"Land: {result.components.land}",
        f"Ocean: {result.components.ocean}",
        f"Agriculture: {result.components.agriculture}",
        f"Sensitivity: {result.components.sensitivity}",
        "",
    ]
    g = result.gee_features
    if g.ndvi_mean is not None or g.soil_moisture_proxy is not None:
        lines.extend(
            [
                "Agriculture surface proxies",
                f"NDVI mean: {g.ndvi_mean}",
                f"Soil moisture proxy: {g.soil_moisture_proxy}",
            ]
        )
    lines.extend(
        [
            "Key Flags",
            *(result.flags or ["None"]),
            "",
            "Interpretation",
            result.interpretation,
            "",
            "Key Insights",
        ]
    )

    for insight in insights:
        lines.append(f"{insight.category.replace('_', ' ').title()}: {insight.message}")

    if result.industrial_verification is not None:
        iv = result.industrial_verification
        lines.extend(["", "Industrial verification (same audit id)", f"Linked: {iv.linked_audit_id}"])
        if iv.nearest_primary_audit is not None:
            n = iv.nearest_primary_audit
            lines.append(f"Nearest Primary Audit: {n.facility_name_tr} ({n.facility_id}) {n.distance_km} km")
        else:
            lines.append("Nearest Primary Audit: none in range")
        for p in iv.pipelines:
            lines.append(f"Pipeline {p.id}: {p.methodology_doc}")

    lines.extend(
        [
            "",
            "Audit",
            f"ID: {result.audit_id}",
            f"Generated: {result.generated_at.isoformat()}",
        ]
    )

    wrapped_lines = []
    for line in lines:
        wrapped_lines.extend(textwrap.wrap(str(line), width=86) or [""])

    pdf = pydyf.PDF()
    font = pydyf.Dictionary(
        {
            "Type": "/Font",
            "Subtype": "/Type1",
            "BaseFont": "/Helvetica",
        }
    )
    pdf.add_object(font)

    content = pydyf.Stream()
    content.begin_text()
    content.set_font_size("F1", 11)
    content.move_text_to(54, 750)

    for index, line in enumerate(wrapped_lines[:52]):
        if index:
            content.move_text_to(0, -14)
        content.show_text_string(line)

    content.end_text()
    pdf.add_object(content)

    page = pydyf.Dictionary(
        {
            "Type": "/Page",
            "Parent": pdf.pages.reference,
            "MediaBox": pydyf.Array([0, 0, 612, 792]),
            "Resources": pydyf.Dictionary(
                {
                    "Font": pydyf.Dictionary({"F1": font.reference}),
                }
            ),
            "Contents": content.reference,
        }
    )
    pdf.add_page(page)

    output = BytesIO()
    pdf.write(output)
    return output.getvalue()
