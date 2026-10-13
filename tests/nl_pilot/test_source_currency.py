"""Source-version currency gate for the pinned Amsterdam Omgevingsplan.

CVDR696291/15 is superseded on 2026-10-14 by Gemeenteblad 2026, 430670.
Claims dated before that stand; claims on or after it fail closed until the
successor consolidated version is sealed and the hemelwater mappings are
re-verified.
"""

from __future__ import annotations

import copy
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.nl_pilot import pilot_evidence_pack
from app.nl_pilot.amsterdam_source import (
    AMSTERDAM_OMGEVINGSPLAN_RESOLVED_REF,
    AMSTERDAM_SOURCE_SUPERSESSIONS,
    CURRENCY_CURRENT,
    CURRENCY_CURRENT_PENDING_SUPERSESSION,
    CURRENCY_NOT_YET_IN_FORCE,
    CURRENCY_SUPERSEDED,
    CURRENCY_UNDETERMINED,
    SOURCE_CURRENCY_AS_OF_INVALID,
    SOURCE_VERSION_NOT_YET_IN_FORCE,
    SOURCE_VERSION_SUPERSEDED,
    SOURCE_VERSION_UNRECOGNIZED,
    SourceVersionNotCurrentError,
    SourceVersionSupersession,
    assess_source_currency,
    require_current_law_claim,
)
from app.nl_pilot.evidence_truth import (
    check_pack_current_law_claim,
    validate_evidence_pack_v2,
)

REF = AMSTERDAM_OMGEVINGSPLAN_RESOLVED_REF
COMMITTED_PACK = Path("data/nl_pilot/evidence-pack-amsterdam-v2.json")


@pytest.fixture(scope="module")
def committed_pack() -> dict:
    return json.loads(COMMITTED_PACK.read_text())


class TestRegistry:
    def test_pinned_version_has_recorded_successor(self):
        s = [x for x in AMSTERDAM_SOURCE_SUPERSESSIONS if x.superseded_ref == REF]
        assert len(s) == 1
        assert s[0].superseding_publication == "gmb-2026-430670"
        assert s[0].effective_from == "2026-10-14"
        assert s[0].last_current_date == "2026-10-13"

    def test_unsealed_notice_is_labelled(self):
        for s in AMSTERDAM_SOURCE_SUPERSESSIONS:
            assert s.evidence_status == "unsealed_official_notice"
            assert s.successor_consolidated_ref is None

    def test_reported_unamended_articles_cannot_be_asserted_verified(self):
        with pytest.raises(TypeError):
            SourceVersionSupersession(  # type: ignore[call-arg]
                superseded_ref=REF,
                superseding_publication="x",
                superseding_publication_url="x",
                superseding_title="x",
                decision_date="2026-09-02",
                publication_date="2026-09-15",
                effective_from="2026-10-14",
                evidence_status="x",
                successor_consolidated_ref=None,
                reported_unamended_articles=(),
                reported_unamended_verified=True,
            )
        for s in AMSTERDAM_SOURCE_SUPERSESSIONS:
            assert s.reported_unamended_verified is False


class TestAssessment:
    def test_day_before_effective_date_is_permitted_but_pending(self):
        a = assess_source_currency(REF, "2026-10-13")
        assert a.current_law_claim_permitted is True
        assert a.currency_state == CURRENCY_CURRENT_PENDING_SUPERSESSION
        assert a.blocker_code is None
        assert a.required_actions

    @pytest.mark.parametrize("as_of", [
        "2026-10-14",
        "2026-10-14T00:00:00+00:00",
        date(2026, 10, 14),
        datetime(2027, 1, 1, tzinfo=timezone.utc),
    ])
    def test_on_or_after_effective_date_fails_closed(self, as_of):
        a = assess_source_currency(REF, as_of)
        assert a.current_law_claim_permitted is False
        assert a.currency_state == CURRENCY_SUPERSEDED
        assert a.blocker_code == SOURCE_VERSION_SUPERSEDED
        assert any("re-verify" in r for r in a.required_actions)

    def test_require_raises_with_named_blocker(self):
        with pytest.raises(SourceVersionNotCurrentError) as exc:
            require_current_law_claim(REF, "2026-10-14")
        assert exc.value.blocker_code == SOURCE_VERSION_SUPERSEDED
        assert "gmb-2026-430670" in str(exc.value)

    @pytest.mark.parametrize("as_of", [
        "", "not-a-date", None, "2026-13-40",
        "2026-10-13T99:99:99", "2026-10-13garbage", "2026-10-13 ",
    ])
    def test_unparseable_as_of_refuses(self, as_of):
        a = assess_source_currency(REF, as_of)
        assert a.current_law_claim_permitted is False
        assert a.currency_state == CURRENCY_UNDETERMINED
        assert a.blocker_code == SOURCE_CURRENCY_AS_OF_INVALID
        with pytest.raises(SourceVersionNotCurrentError):
            require_current_law_claim(REF, as_of)

    @pytest.mark.parametrize("ref", ["CVDR696291/16", "CVDR696291/14", "", "cvdr696291/15"])
    def test_unregistered_ref_refuses(self, ref):
        a = assess_source_currency(ref, "2026-10-01")
        assert a.current_law_claim_permitted is False
        assert a.currency_state == CURRENCY_UNDETERMINED
        assert a.blocker_code == SOURCE_VERSION_UNRECOGNIZED
        with pytest.raises(SourceVersionNotCurrentError):
            require_current_law_claim(ref, "2026-10-01")

    @pytest.mark.parametrize("as_of", ["2026-01-01", "2026-06-18"])
    def test_before_pinned_version_took_effect_refuses(self, as_of):
        a = assess_source_currency(REF, as_of)
        assert a.current_law_claim_permitted is False
        assert a.currency_state == CURRENCY_NOT_YET_IN_FORCE
        assert a.blocker_code == SOURCE_VERSION_NOT_YET_IN_FORCE

    def test_pinned_version_effective_day_is_permitted(self):
        a = assess_source_currency(REF, "2026-06-19")
        assert a.current_law_claim_permitted is True
        assert a.currency_state == CURRENCY_CURRENT_PENDING_SUPERSESSION


class TestPack:
    def test_committed_pack_records_pending_supersession(self, committed_pack):
        sc = committed_pack["source_currency"]
        assert sc["currency_state"] == CURRENCY_CURRENT_PENDING_SUPERSESSION
        assert sc["supersession"]["effective_from"] == "2026-10-14"
        assert sc["supersession"]["reported_unamended_verified"] is False
        not_verified = committed_pack["truth_state"]["claim_boundaries"]["not_verified"]
        assert any("on or after 2026-10-14" in x for x in not_verified)

    def test_consumer_gate_before_and_after(self, committed_pack):
        check_pack_current_law_claim(committed_pack, "2026-10-13")
        with pytest.raises(SourceVersionNotCurrentError) as exc:
            check_pack_current_law_claim(committed_pack, "2026-10-14")
        assert exc.value.blocker_code == SOURCE_VERSION_SUPERSEDED

    def test_consumer_gate_refuses_historical_date(self, committed_pack):
        with pytest.raises(SourceVersionNotCurrentError) as exc:
            check_pack_current_law_claim(committed_pack, "2026-01-01")
        assert exc.value.blocker_code == SOURCE_VERSION_NOT_YET_IN_FORCE

    def test_consumer_gate_refuses_retargeted_version_ref(self, committed_pack):
        bad = copy.deepcopy(committed_pack)
        bad["source_provenance"]["regulatory_source"]["resolved_version_ref"] = "CVDR696291/16"
        with pytest.raises(SourceVersionNotCurrentError) as exc:
            check_pack_current_law_claim(bad, "2026-10-20")
        assert exc.value.blocker_code == SOURCE_VERSION_UNRECOGNIZED

    def test_validator_rejects_retargeted_version_ref(self, committed_pack):
        bad = copy.deepcopy(committed_pack)
        bad["source_provenance"]["regulatory_source"]["resolved_version_ref"] = "CVDR696291/16"
        with pytest.raises(ValueError, match=SOURCE_VERSION_UNRECOGNIZED):
            validate_evidence_pack_v2(bad)

    def test_consumer_gate_refuses_pack_without_version_ref(self):
        with pytest.raises(ValueError):
            check_pack_current_law_claim({}, "2026-10-01")

    def test_validator_rejects_pack_dated_after_supersession(self, committed_pack):
        bad = copy.deepcopy(committed_pack)
        bad["evidence_as_of"] = "2026-10-14T09:00:00+00:00"
        with pytest.raises(ValueError, match=SOURCE_VERSION_SUPERSEDED):
            validate_evidence_pack_v2(bad)

    def test_validator_rejects_stripped_currency_block(self, committed_pack):
        bad = copy.deepcopy(committed_pack)
        bad.pop("source_currency")
        with pytest.raises(ValueError, match="source_currency"):
            validate_evidence_pack_v2(bad)

    def test_validator_rejects_promoted_currency_block(self, committed_pack):
        bad = copy.deepcopy(committed_pack)
        bad["source_currency"]["currency_state"] = CURRENCY_CURRENT
        bad["source_currency"]["supersession"] = None
        with pytest.raises(ValueError, match="source_currency"):
            validate_evidence_pack_v2(bad)

    def test_build_fails_closed_when_evidence_postdates_successor(self, monkeypatch):
        monkeypatch.setattr(
            pilot_evidence_pack,
            "_determine_evidence_as_of",
            lambda manifest: "2026-10-14T00:00:00+00:00",
        )
        with pytest.raises(SourceVersionNotCurrentError) as exc:
            pilot_evidence_pack.build_pilot_evidence_pack()
        assert exc.value.blocker_code == SOURCE_VERSION_SUPERSEDED
