"""Article 4.113 — Toepassingsbereik (Applicability Scope) State Machine.

Implements fail-closed legal applicability evaluation for Amsterdam
pilot assets under CVDR696291/15.

Core invariants:
  - municipality_match=true is a candidate condition ONLY
  - municipality_match=true MUST NOT imply applicable=true
  - Missing evidence produces null (indeterminate), NOT false
  - A failed trigger does NOT preclude other trigger families
  - All verification states are produced by the state machine,
    not by callers
  - Legal decision (paragraph_applicable) is separate from
    evidence verification (asset_applicability_verified)

Architecture:
  Article4113Evidence (input facts)
  → evaluate_article_4_113()
  → Article4113Decision (three-valued output)

Fail-closed:
  Unknown evidence → indeterminate
  Out of jurisdiction → not_applicable (false)
  True applicability → only when ALL evidence verified AND
      transition exclusions cleared

Classification: legal analysis — NOT production decision
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


# ---------------------------------------------------------------------------
# Evidence model — tri-state fact representation
# ---------------------------------------------------------------------------

@dataclass
class Article4113Evidence:
    """Facts required for Article 4.113 applicability evaluation.

    Every Optional[bool] field uses tri-state semantics:
      True  = verified evidence establishes the fact
      False = verified evidence establishes negation
      None  = evidence absent or insufficient

    Do NOT default missing evidence to False.
    """

    # --- Jurisdiction ---
    municipality_match: Optional[bool] = None
    water_authority_match: Optional[bool] = None

    # --- Trigger family A: New building (Art. 4.113(2)(a)) ---
    building_is_new: Optional[bool] = None

    # --- Trigger family B(1): Major renovation (Art. 4.113(2)(b)(1)) ---
    major_renovation: Optional[bool] = None
    major_renovation_date: Optional[str] = None  # ISO date or None
    # Verified whole-building bruto vloeroppervlak (NOT VBO floor area)
    building_gross_floor_area_m2: Optional[float] = None

    # --- Trigger family B(2): Additional layer/cellar/souterrain ---
    building_layer_added: Optional[bool] = None
    building_layer_added_date: Optional[str] = None
    cellar_or_souterrain_added: Optional[bool] = None
    cellar_or_souterrain_event_date: Optional[str] = None

    # --- Trigger family B(3): Roof extension / dakopbouw ---
    roof_extension: Optional[bool] = None
    roof_extension_date: Optional[str] = None
    roof_extension_area_m2: Optional[float] = None
    # Verified main-building bebouwd oppervlak (NOT VBO floor area)
    main_building_built_area_m2: Optional[float] = None

    # --- Trigger family B(4): Expansion of bebouwd oppervlak ---
    built_area_expansion: Optional[bool] = None
    built_area_expansion_date: Optional[str] = None

    # --- Cellar extension specifics ---
    cellar_extension: Optional[bool] = None
    cellar_extension_area_m2: Optional[float] = None
    cellar_extension_date: Optional[str] = None  # ISO date for extension event
    cellar_deepened_for_use: Optional[bool] = None
    cellar_deepening_date: Optional[str] = None  # ISO date for deepening event

    # --- Transitional exclusions (Art. 4.113 overgangsrecht) ---
    permit_application_before_2021_05_11: Optional[bool] = None
    land_selection_or_development_agreement_before_2021_06_22: Optional[bool] = None

    # --- Evidence provenance ---
    evidence_refs: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Decision model — three-valued output
# ---------------------------------------------------------------------------

# Allowed applicability states
APPLICABLE = "applicable"
NOT_APPLICABLE = "not_applicable"
INDETERMINATE = "indeterminate"
OUTSIDE_JURISDICTION = "outside_jurisdiction"

# The cutoff date for Article 4.113 trigger families
ART_4_113_CUTOFF_DATE = date(2021, 5, 11)

# Article 4.113 absolute area threshold for dakopbouw (groter dan 100 m²)
ART_4_113_DAKOPBOUW_ABSOLUTE_M2 = 100.0

# Article 4.113 renovation BVO threshold
ART_4_113_RENOVATION_BVO_M2 = 1000.0


@dataclass
class Article4113Decision:
    """Three-valued Article 4.113 applicability decision.

    paragraph_applicable:
      True  = Article 4.113 confirmed applicable
      False = Article 4.113 confirmed not applicable
      None  = indeterminate (evidence incomplete)

    NOTE: asset_applicability_verified is SEPARATE from paragraph_applicable.
    Synthetic/computed applicability != verified asset-level evidence.
    A dedicated sealed-evidence verification path is required to promote
    asset_applicability_verified to True.
    """

    municipality_match: bool
    applicability_candidate: bool

    paragraph_scope_article: str = "Artikel 4.113"
    paragraph_applicable: Optional[bool] = None
    # NOTE: kept False until sealed asset-level evidence factory exists.
    # Synthetic/computed applicability != verified asset-level evidence.
    asset_applicability_verified: bool = False
    applicability_state: str = INDETERMINATE

    trigger: Optional[str] = None
    transition_exemption: Optional[str] = None

    missing_evidence: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    reason_code: str = "ARTICLE_4_113_EVIDENCE_INCOMPLETE"

    # Sub-decisions for each trigger family (for debugging/audit)
    trigger_decisions: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def tri_state_any(values: list[Optional[bool]]) -> Optional[bool]:
    """Tri-state OR aggregation for a list of Optional[bool] values.

    ANY True  -> True
    NO True + ANY None -> None
    ALL False -> False

    Do not early-return None before checking other OR limbs.
    """
    if any(v is True for v in values):
        return True
    if any(v is None for v in values):
        return None
    return False


def _date_after_cutoff(date_str: Optional[str]) -> Optional[bool]:
    """Check if a date string is strictly after the Art. 4.113 cutoff.

    Uses proper ISO date parsing instead of lexical string comparison.
    Invalid date strings return None (indeterminate), not True.
    """
    if date_str is None:
        return None
    try:
        event_date = date.fromisoformat(date_str)
    except (TypeError, ValueError):
        return None
    return event_date > ART_4_113_CUTOFF_DATE


# ---------------------------------------------------------------------------
# Trigger family evaluators
# ---------------------------------------------------------------------------

def _evaluate_new_building(evidence: Article4113Evidence) -> dict:
    """Evaluate trigger family A: new building (Art. 4.113(2)(a))."""
    if evidence.building_is_new is None:
        return {
            "trigger": None,
            "applicable": None,
            "missing": ["building_is_new"],
        }
    if evidence.building_is_new:
        return {
            "trigger": "new_building",
            "applicable": True,
            "missing": [],
        }
    return {
        "trigger": None,
        "applicable": False,
        "missing": [],
    }


def _evaluate_major_renovation(evidence: Article4113Evidence) -> dict:
    """Evaluate trigger family B(1): major renovation (Art. 4.113(2)(b)(1)).

    Requires:
      - major_renovation = True
      - event_date > 2021-05-11
      - building_gross_floor_area_m2 >= 1000

    NOTE: oppervlakte_m2 is VBO floor area, NOT building BVO.
    """
    missing = []

    if evidence.major_renovation is None:
        missing.append("major_renovation")
        return {
            "trigger": None,
            "applicable": None,
            "missing": missing,
        }

    if not evidence.major_renovation:
        return {
            "trigger": None,
            "applicable": False,
            "missing": [],
        }

    # major_renovation is True — check date
    date_ok = _date_after_cutoff(evidence.major_renovation_date)
    if date_ok is None:
        missing.append("major_renovation_date")
        # Date unknown → cannot evaluate this trigger yet
        return {
            "trigger": None,
            "applicable": None,
            "missing": missing,
        }
    if not date_ok:
        return {
            "trigger": None,
            "applicable": False,
            "missing": [],
        }

    # Check BVO
    if evidence.building_gross_floor_area_m2 is None:
        missing.append("building_gross_floor_area_m2")
        return {
            "trigger": None,
            "applicable": None,
            "missing": missing,
        }

    if evidence.building_gross_floor_area_m2 < ART_4_113_RENOVATION_BVO_M2:
        return {
            "trigger": None,
            "applicable": False,
            "missing": [],
        }

    return {
        "trigger": "major_renovation",
        "applicable": True,
        "missing": [],
    }


def _evaluate_layer_or_cellar(evidence: Article4113Evidence) -> dict:
    """Evaluate trigger family B(2): additional layer/cellar/souterrain.

    OR aggregation of independent limbs:
      - building_layer_added + date
      - cellar_or_souterrain_added + date

    Tri-state OR rules:
      ANY TRUE  -> TRUE
      NO TRUE + ANY UNKNOWN -> NONE
      ALL FALSE -> FALSE

    Do not early-return before checking other OR limbs.
    """
    missing = []
    limb_results: list[Optional[bool]] = []
    limb_triggers: list[Optional[str]] = []

    # Limb 1: building layer
    has_layer = evidence.building_layer_added
    if has_layer is None:
        missing.append("building_layer_added")
        limb_results.append(None)
        limb_triggers.append(None)
    elif not has_layer:
        limb_results.append(False)
        limb_triggers.append(None)
    else:
        # has_layer is True — check date
        date_ok = _date_after_cutoff(evidence.building_layer_added_date)
        if date_ok is None:
            missing.append("building_layer_added_date")
            limb_results.append(None)
            limb_triggers.append(None)
        elif not date_ok:
            limb_results.append(False)
            limb_triggers.append(None)
        else:
            limb_results.append(True)
            limb_triggers.append("additional_layer")

    # Limb 2: cellar/souterrain
    has_cellar = evidence.cellar_or_souterrain_added
    if has_cellar is None:
        missing.append("cellar_or_souterrain_added")
        limb_results.append(None)
        limb_triggers.append(None)
    elif not has_cellar:
        limb_results.append(False)
        limb_triggers.append(None)
    else:
        # has_cellar is True — check date
        date_ok = _date_after_cutoff(evidence.cellar_or_souterrain_event_date)
        if date_ok is None:
            missing.append("cellar_or_souterrain_event_date")
            limb_results.append(None)
            limb_triggers.append(None)
        elif not date_ok:
            limb_results.append(False)
            limb_triggers.append(None)
        else:
            limb_results.append(True)
            limb_triggers.append("cellar_souterrain_added")

    # Aggregate: tri-state OR
    combined = tri_state_any(limb_results)

    if combined is True:
        # Find which trigger fired
        trigger_name = next(
            (t for t in limb_triggers if t is not None), None
        )
        return {
            "trigger": trigger_name,
            "applicable": True,
            "missing": missing,
        }
    elif combined is None:
        return {
            "trigger": None,
            "applicable": None,
            "missing": missing,
        }
    else:
        return {
            "trigger": None,
            "applicable": False,
            "missing": missing,
        }


def _evaluate_dakopbouw(evidence: Article4113Evidence) -> dict:
    """Evaluate trigger family B(3): roof extension / dakopbouw.

    Requires:
      - roof_extension after 2021-05-11
      - AND at least one size condition:
        - roof_extension_area_m2 > 100 m² (absolute), OR
        - roof_extension_area_m2 > 50% of main_building_built_area_m2

    When both size facts are known and both limbs deterministically
    fail, return False (not None).
    """
    missing = []

    if evidence.roof_extension is None:
        missing.append("roof_extension")
        return {
            "trigger": None,
            "applicable": None,
            "missing": missing,
        }

    if not evidence.roof_extension:
        return {
            "trigger": None,
            "applicable": False,
            "missing": [],
        }

    # roof_extension is True — check date
    date_ok = _date_after_cutoff(evidence.roof_extension_date)
    if date_ok is None:
        missing.append("roof_extension_date")
        return {
            "trigger": None,
            "applicable": None,
            "missing": missing,
        }
    if not date_ok:
        return {
            "trigger": None,
            "applicable": False,
            "missing": [],
        }

    # Check size conditions — tri-state OR of two limbs
    area = evidence.roof_extension_area_m2
    built_area = evidence.main_building_built_area_m2

    # Limb 1: absolute (> 100 m²)
    abs_limb: Optional[bool] = None
    if area is not None:
        abs_limb = area > ART_4_113_DAKOPBOUW_ABSOLUTE_M2

    # Limb 2: relative (> 50% of main building built area)
    rel_limb: Optional[bool] = None
    if area is not None and built_area is not None and built_area > 0:
        rel_limb = area > 0.5 * built_area
    elif area is not None and built_area is not None and built_area <= 0:
        # 0 or negative built area → 50% limb cannot be satisfied
        rel_limb = False

    # Track missing evidence for size limbs
    if area is None:
        missing.append("roof_extension_area_m2")
    if built_area is None:
        missing.append("main_building_built_area_m2")

    combined = tri_state_any([abs_limb, rel_limb])

    if combined is True:
        return {
            "trigger": "dakopbouw",
            "applicable": True,
            "missing": missing,
        }
    elif combined is None:
        return {
            "trigger": None,
            "applicable": None,
            "missing": missing,
        }
    else:
        # Both limbs deterministically false
        return {
            "trigger": None,
            "applicable": False,
            "missing": missing,
        }


def _evaluate_built_area_expansion(evidence: Article4113Evidence) -> dict:
    """Evaluate trigger family B(4): expansion of bebouwd oppervlak.

    Requires verified evidence that after 2021-05-11 bebouwd oppervlak
    was expanded. VBO floor area cannot prove this event.
    """
    missing = []

    if evidence.built_area_expansion is None:
        missing.append("built_area_expansion")
        return {
            "trigger": None,
            "applicable": None,
            "missing": missing,
        }

    if not evidence.built_area_expansion:
        return {
            "trigger": None,
            "applicable": False,
            "missing": [],
        }

    # built_area_expansion is True — check date
    date_ok = _date_after_cutoff(evidence.built_area_expansion_date)
    if date_ok is None:
        missing.append("built_area_expansion_date")
        return {
            "trigger": None,
            "applicable": None,
            "missing": missing,
        }
    if not date_ok:
        return {
            "trigger": None,
            "applicable": False,
            "missing": [],
        }

    return {
        "trigger": "built_area_expansion",
        "applicable": True,
        "missing": [],
    }


def _evaluate_cellar_extension(evidence: Article4113Evidence) -> dict:
    """Evaluate cellar extension / deepening under Art. 4.113.

    Article 4.113 paragraph 4 treats cellar/souterrain enlargement/
    deepening as part of paragraph 2(b)(2).  The post-11-May-2021
    cutoff still applies.

    Size/use limbs (tri-state OR):
      - extension > 50% of main-building bebouwd oppervlak
      - extension has minimum size 100 m² (>= 100)
      - existing cellar/souterrain is deepened into usable Bbl space

    Each limb requires its own event date to be after the cutoff.
    VBO oppervlakte_m2 must not be used as main-building bebouwd oppervlak.
    """
    missing: list[str] = []

    if evidence.cellar_extension is None and evidence.cellar_deepened_for_use is None:
        missing.append("cellar_extension")
        missing.append("cellar_deepened_for_use")
        return {
            "trigger": None,
            "applicable": None,
            "missing": missing,
        }

    # --- Cellar extension event ---
    ext_evaluated: Optional[bool] = None
    if evidence.cellar_extension is True:
        # Check cutoff date for the extension event
        ext_date_ok = _date_after_cutoff(evidence.cellar_extension_date)
        if ext_date_ok is None:
            missing.append("cellar_extension_date")
            ext_evaluated = None  # date unknown → cannot decide
        elif not ext_date_ok:
            # Pre-cutoff extension → does not trigger
            ext_evaluated = False
        else:
            # Post-cutoff extension — check size limbs
            ext_area = evidence.cellar_extension_area_m2
            built_area = evidence.main_building_built_area_m2

            # Limb 1: absolute (>= 100 m²)
            abs_limb: Optional[bool] = None
            if ext_area is not None:
                abs_limb = ext_area >= ART_4_113_DAKOPBOUW_ABSOLUTE_M2

            # Limb 2: relative (> 50%)
            rel_limb: Optional[bool] = None
            if ext_area is not None and built_area is not None and built_area > 0:
                rel_limb = ext_area > 0.5 * built_area
            elif ext_area is not None and built_area is not None and built_area <= 0:
                rel_limb = False

            if ext_area is None:
                missing.append("cellar_extension_area_m2")
            if built_area is None:
                missing.append("main_building_built_area_m2")

            ext_evaluated = tri_state_any([abs_limb, rel_limb])

    elif evidence.cellar_extension is False:
        ext_evaluated = False
    # else: cellar_extension is None → ext_evaluated stays None

    # --- Deepening for Bbl use ---
    deep_evaluated: Optional[bool] = None
    if evidence.cellar_deepened_for_use is True:
        # Check cutoff date for the deepening event
        deep_date_ok = _date_after_cutoff(evidence.cellar_deepening_date)
        if deep_date_ok is None:
            missing.append("cellar_deepening_date")
            deep_evaluated = None
        elif not deep_date_ok:
            deep_evaluated = False
        else:
            deep_evaluated = True
    elif evidence.cellar_deepened_for_use is False:
        deep_evaluated = False
    # else: cellar_deepened_for_use is None → deep_evaluated stays None

    # --- Aggregate OR of extension + deepening ---
    combined = tri_state_any([ext_evaluated, deep_evaluated])

    if combined is True:
        # Determine which trigger fired
        if ext_evaluated is True:
            trigger_name = "cellar_extension"
        else:
            trigger_name = "cellar_deepened"
        return {
            "trigger": trigger_name,
            "applicable": True,
            "missing": missing,
        }
    elif combined is None:
        return {
            "trigger": None,
            "applicable": None,
            "missing": missing,
        }
    else:
        return {
            "trigger": None,
            "applicable": False,
            "missing": missing,
        }


# ---------------------------------------------------------------------------
# Transition exclusions
# ---------------------------------------------------------------------------

def _check_transition_exclusions(evidence: Article4113Evidence) -> tuple:
    """Check transitional exclusions under Art. 4.113 overgangsrecht.

    Returns (exemption_applied, exemption_reason, missing_evidence).
    """
    missing = []
    permit_before = evidence.permit_application_before_2021_05_11
    dev_before = evidence.land_selection_or_development_agreement_before_2021_06_22

    if permit_before is True:
        return (
            True,
            "TRANSITION_PRE_2021_05_11_PERMIT",
            [],
        )

    if dev_before is True:
        return (
            True,
            "TRANSITION_PRE_2021_06_22_DEVELOPMENT_AGREEMENT",
            [],
        )

    if permit_before is None:
        missing.append("permit_application_before_2021_05_11")
    if dev_before is None:
        missing.append("land_selection_or_development_agreement_before_2021_06_22")

    return (False, None, missing)


# ---------------------------------------------------------------------------
# Main state machine
# ---------------------------------------------------------------------------

def evaluate_article_4_113(
    municipality: str,
    evidence: Article4113Evidence | None = None,
) -> Article4113Decision:
    """Evaluate Article 4.113 applicability for an asset.

    Parameters
    ----------
    municipality : str
        Asset municipality from BAG identity.
    evidence : Article4113Evidence | None
        Verified legal-event evidence.  None means no evidence available
        (all triggers indeterminate).

    Returns
    -------
    Article4113Decision
        Three-valued applicability decision with full audit trail.

    NOTE: asset_applicability_verified is ALWAYS False in this function.
    Synthetic/computed applicability != verified asset-level evidence.
    A dedicated sealed-evidence verification path is required to promote
    asset_applicability_verified to True.
    """
    if evidence is None:
        evidence = Article4113Evidence()

    # --- Step 1: Jurisdiction candidate ---
    municipality_match = (municipality == "Amsterdam")

    if not municipality_match:
        return Article4113Decision(
            municipality_match=False,
            applicability_candidate=False,
            paragraph_applicable=False,
            asset_applicability_verified=False,
            applicability_state=OUTSIDE_JURISDICTION,
            reason_code="OUTSIDE_JURISDICTION",
        )

    # Municipality matches — evaluate trigger families
    all_missing: list[str] = []
    trigger_decisions: dict[str, dict] = {}

    # --- Step 2: Evaluate trigger families ---
    new_bld = _evaluate_new_building(evidence)
    trigger_decisions["new_building"] = new_bld
    all_missing.extend(new_bld["missing"])

    major_ren = _evaluate_major_renovation(evidence)
    trigger_decisions["major_renovation"] = major_ren
    all_missing.extend(major_ren["missing"])

    layer_cellar = _evaluate_layer_or_cellar(evidence)
    trigger_decisions["layer_cellar"] = layer_cellar
    all_missing.extend(layer_cellar["missing"])

    dakopbouw = _evaluate_dakopbouw(evidence)
    trigger_decisions["dakopbouw"] = dakopbouw
    all_missing.extend(dakopbouw["missing"])

    built_exp = _evaluate_built_area_expansion(evidence)
    trigger_decisions["built_area_expansion"] = built_exp
    all_missing.extend(built_exp["missing"])

    cellar_ext = _evaluate_cellar_extension(evidence)
    trigger_decisions["cellar_extension"] = cellar_ext
    all_missing.extend(cellar_ext["missing"])

    # --- Step 3: Determine if any trigger fires ---
    triggered = [
        td for td in trigger_decisions.values()
        if td["applicable"] is True
    ]
    indeterminate_triggers = [
        td for td in trigger_decisions.values()
        if td["applicable"] is None
    ]

    if not triggered and not indeterminate_triggers:
        # All trigger families evaluated as False
        return Article4113Decision(
            municipality_match=True,
            applicability_candidate=True,
            paragraph_applicable=False,
            asset_applicability_verified=False,
            applicability_state=NOT_APPLICABLE,
            reason_code="NO_TRIGGER_FAMILY_APPLIES",
            trigger_decisions=trigger_decisions,
            missing_evidence=sorted(set(all_missing)),
            evidence_refs=evidence.evidence_refs,
        )

    if not triggered and indeterminate_triggers:
        # No confirmed trigger, some still unknown → indeterminate
        return Article4113Decision(
            municipality_match=True,
            applicability_candidate=True,
            paragraph_applicable=None,
            asset_applicability_verified=False,
            applicability_state=INDETERMINATE,
            reason_code="ARTICLE_4_113_EVIDENCE_INCOMPLETE",
            trigger_decisions=trigger_decisions,
            missing_evidence=sorted(set(all_missing)),
            evidence_refs=evidence.evidence_refs,
        )

    # --- Step 4: A trigger fired — check transition exclusions ---
    trigger_name = triggered[0]["trigger"]

    exemption_applied, exemption_reason, transition_missing = (
        _check_transition_exclusions(evidence)
    )
    all_missing.extend(transition_missing)

    if exemption_applied:
        return Article4113Decision(
            municipality_match=True,
            applicability_candidate=True,
            paragraph_applicable=False,
            asset_applicability_verified=False,
            applicability_state=NOT_APPLICABLE,
            trigger=trigger_name,
            transition_exemption=exemption_reason,
            reason_code=exemption_reason,
            trigger_decisions=trigger_decisions,
            missing_evidence=sorted(set(all_missing)),
            evidence_refs=evidence.evidence_refs,
        )

    if transition_missing:
        # Positive trigger but transition evidence unknown → indeterminate
        return Article4113Decision(
            municipality_match=True,
            applicability_candidate=True,
            paragraph_applicable=None,
            asset_applicability_verified=False,
            applicability_state=INDETERMINATE,
            trigger=trigger_name,
            reason_code="TRANSITION_EVIDENCE_INCOMPLETE",
            trigger_decisions=trigger_decisions,
            missing_evidence=sorted(set(all_missing)),
            evidence_refs=evidence.evidence_refs,
        )

    # --- Step 5: Trigger confirmed AND transition cleared ---
    # NOTE: asset_applicability_verified stays False.
    # Synthetic/computed applicability != verified asset-level evidence.
    # A sealed-evidence verification path is needed to promote this.
    return Article4113Decision(
        municipality_match=True,
        applicability_candidate=True,
        paragraph_applicable=True,
        asset_applicability_verified=False,
        applicability_state=APPLICABLE,
        trigger=trigger_name,
        trigger_decisions=trigger_decisions,
        missing_evidence=sorted(set(all_missing)),
        evidence_refs=evidence.evidence_refs,
        reason_code="ARTICLE_4_113_CONFIRMED",
    )
