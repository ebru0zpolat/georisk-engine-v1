"""Prohibited-claim scanner (spec §11).

Automated claim scanning fails the build when a prohibited term appears outside a quotation
or a control/comparison table. The scanner is deliberately conservative: it flags on the
prohibited phrase and then clears the hit only when the phrase sits in a genuine permitted
context — a fenced block, a Markdown blockquote, a quoted span in prose, or a Markdown
table row (a control table).

JSON bodies are scanned literally: every JSON string value is a candidate claim, so the
quotation/table exemptions do NOT apply there. Otherwise the double quotes that delimit
every JSON string would mark every line a "quotation" and suppress every finding — e.g. a
project ``objective`` set to a prohibited phrase would seal silently.
"""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, Field


class ClaimSeverity(str, Enum):
    prohibited = "prohibited"


#: Prohibited phrases (spec §11 "Prohibited wording" column), lower-cased for matching.
PROHIBITED_PHRASES: tuple[str, ...] = (
    "cmb compliant",
    "cmb-compliant",
    "cmb approved",
    "cmb-approved",
    "cmb certified",
    "cmb-certified",
    "cmb authorised certifier",
    "guaranteed saving",
    "compliance guaranteed",
    "eligible green project determined by georisk",
    "eligible social project determined by georisk",
    "cmb-approved kpi",
    "cmb-approved spt",
    "assured target",
    "prediction of actual loss",
    "complete climate-risk assessment",
    "second-party opinion report",
    "verification report",
    "independently validated empirical accuracy",
    "engineering certification",
    "confirmation of design adequacy",
    "certified compliant",
)

#: Permitted wording pairs (spec §11) — surfaced for the claims register, not enforced here.
PERMITTED_WORDING: dict[str, str] = {
    "regulatory_use": "Supports selected evidence needs under the named CMB guideline",
    "project_eligibility": "Technical evidence for issuer and external-review assessment",
    "kpi_spt": "Candidate KPI/SPT design input; subject to issuer governance and independent review",
    "physical_risk": "Versioned physical-risk proxy under stated data and assumptions",
    "external_review": "Reviewer-oriented evidence bundle",
    "reproducibility": "Independently reproducible calculation record",
    "forward_looking": "Based on named, licensed and versioned scenario data",
    "engineering": "Supports prioritisation and further investigation",
}


class ClaimFinding(BaseModel):
    """One prohibited-term hit outside a permitted context."""

    file: str
    line_number: int
    phrase: str
    line: str
    severity: ClaimSeverity = ClaimSeverity.prohibited


class ClaimScanResult(BaseModel):
    findings: list[ClaimFinding] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.findings

    def summary(self) -> str:
        if self.ok:
            return "claim scan clean"
        return "; ".join(
            f"{f.file}:{f.line_number} prohibited claim '{f.phrase}'" for f in self.findings
        )


_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
#: A span wrapped in straight or curly quotes — the unit that may quote a regulatory phrase.
_QUOTED_SPAN = re.compile(r"\"[^\"]*\"|“[^”]*”|'[^']*'")


def _is_markdown_quotation(line: str) -> bool:
    return line.lstrip().startswith(">")


def _is_control_table(line: str) -> bool:
    return bool(_TABLE_ROW.match(line))


def _phrase_in_quoted_span(line: str, phrase: str) -> bool:
    """True only when the prohibited phrase itself sits inside a quoted span.

    Unlike a blanket "line contains a quote character" test, this requires the phrase to be
    the quoted content, so an unrelated apostrophe elsewhere on the line cannot exempt it.
    """
    return any(phrase in match.group(0).casefold() for match in _QUOTED_SPAN.finditer(line))


def _in_permitted_markdown_context(line: str, phrase: str) -> bool:
    return (
        _is_markdown_quotation(line)
        or _is_control_table(line)
        or _phrase_in_quoted_span(line, phrase)
    )


def scan_text(text: str, *, file: str = "<text>") -> ClaimScanResult:
    """Scan ``text`` for prohibited claims outside permitted contexts (spec §11).

    JSON bodies (``file`` ending ``.json``) are scanned literally with no quotation/table
    exemption — a prohibited phrase in any JSON string value is a finding.
    """
    findings: list[ClaimFinding] = []
    is_json = file.casefold().endswith(".json")
    in_fenced_block = False
    for idx, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line
        stripped = line.strip()
        if not is_json and stripped.startswith("```"):
            in_fenced_block = not in_fenced_block
            continue
        if in_fenced_block:
            # Fenced code / quoted regulatory text is a permitted context.
            continue
        lowered = line.casefold()
        for phrase in PROHIBITED_PHRASES:
            if phrase not in lowered:
                continue
            if not is_json and _in_permitted_markdown_context(line, phrase):
                continue
            findings.append(
                ClaimFinding(file=file, line_number=idx, phrase=phrase, line=stripped)
            )
    return ClaimScanResult(findings=findings)


def scan_bundle(files: dict[str, str]) -> ClaimScanResult:
    """Scan every file body in a rendered bundle (filename → text)."""
    all_findings: list[ClaimFinding] = []
    for name, body in files.items():
        all_findings.extend(scan_text(body, file=name).findings)
    return ClaimScanResult(findings=all_findings)


__all__ = [
    "ClaimFinding",
    "ClaimScanResult",
    "ClaimSeverity",
    "PERMITTED_WORDING",
    "PROHIBITED_PHRASES",
    "scan_bundle",
    "scan_text",
]
