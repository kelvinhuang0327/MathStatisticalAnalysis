"""Cross-model and historical/current identity regressions for repaired K20 bounds."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from lottolab.research import b649_k20_canonical_single_count_reconciliation_r1 as repair
from lottolab.research import b649_k20_heavy_pair_defect_global_bound_r2 as heavy
from lottolab.research import b649_official_any_prize_exact as exact

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_published_authority_matches_live_analytical_recomputation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("no solver or full portfolio exact evaluation authorized")

    monkeypatch.setattr(heavy, "_cp_model_api", forbidden)
    monkeypatch.setattr(exact, "evaluate_portfolio", forbidden)
    expected = repair.build_authority_record()
    # JSON-normalize tuples once; no second mathematical replay for byte tests.
    serialized = json.dumps(expected, sort_keys=True, separators=(",", ":"))
    assert _read(repair.RECORD) == json.loads(serialized)
    assert serialized == json.dumps(json.loads(serialized), sort_keys=True, separators=(",", ":"))


def test_current_authority_uses_sealed_incumbent_and_reopens_five_claims() -> None:
    record = _read(repair.RECORD)
    assert record["CANONICAL_SINGLE_OUTCOMES"] == 18_611_432
    assert record["CROSS_INVARIANTS"] == {
        "closed_form": 18_611_432,
        "identical_ticket_intersection": 18_611_432,
        "seven_set_formula": 18_611_432,
        "K20_S1": 372_228_640,
    }
    assert record["INCUMBENT_EXACT_COUNT"] == 313_263_888
    assert record["INCUMBENT_PORTFOLIO_SHA256"] == (
        "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"
    )
    expected = {
        "OUTSIDE_PAIR_LE1": 319_242_373,
        "FAMILY_C": 319_306_232,
        "TWO_SHARED_VERTEX": 319_531_968,
        "TWO_DISJOINT": 319_477_816,
        "THREE_OR_MORE_AT_MASS_93": 313_736_640,
    }
    assert record["CLOSED_SCOPE_TRANSITIONS"].keys() == expected.keys()
    for name, bound in expected.items():
        row = record["CLOSED_SCOPE_TRANSITIONS"][name]
        assert row["corrected_upper_bound"] == bound
        assert row["corrected_upper_bound"] - row["historical_upper_bound"] == 7_807_080
        assert row["current_status"] == "OPEN"
    assert record["FAMILY_BOUNDS"]["MIN_S2"]["upper_bound"] == 313_916_056
    assert record["FAMILY_BOUNDS"]["FAMILY_A"]["upper_bound"] == 365_048_628
    assert record["FAMILY_BOUNDS"]["FAMILY_B"]["upper_bound"] == 365_601_423
    assert record["K20_GLOBAL_CERTIFIED_BOUND"] == 365_601_423
    assert record["K20_REMAINING_GAP"] == 52_337_535
    for row in record["FAMILY_BOUNDS"].values():
        assert row["status"] == ("CLOSED" if row["upper_bound"] <= 313_263_888 else "OPEN")
    by_count = record["MASS_93_SUBFAMILIES_BY_HEAVY_COUNT"]
    assert sorted(int(h) for h, row in by_count.items() if row["status"] == "OPEN") == [3, 4, 5, 6]
    assert by_count["6"]["gap_to_incumbent"] == 1_288
    assert record["CP_SAT"] == record["PILOT"] == record["NEW_PORTFOLIO_SEARCH"] == "NOT_RUN"
    assert record["NEW_FULL_EXACT_EVALUATIONS"] == 0
    assert record["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert record["CP_SAT_EVIDENCE_POLICY"].startswith("NOT_REVALIDATED_NOT_ADMITTED")


def test_historical_records_and_explicit_source_revisions_are_bound_to_bytes() -> None:
    record = _read(repair.RECORD)
    for item in record["PRESERVED_HISTORICAL_RECORDS"] + record["CURRENT_IMPLEMENTATION_FILES"]:
        content = (ROOT / item["path"]).read_bytes()
        assert len(content) == item["bytes"]
        assert hashlib.sha256(content).hexdigest() == item["sha256"]
    historical = _read(repair.PRIOR_AUTHORITY)
    assert (
        historical["K20_OUTSIDE_PAIR_LE1_STATUS"] == historical["K20_FAMILY_C_STATUS"] == "CLOSED"
    )
    manifest = _read(repair.PRIOR_MANIFEST)
    frozen = {item["path"]: item for item in manifest["COPIED_FILES"]}
    assert {item["path"] for item in record["SOURCE_REVISIONS"]} == repair.REVISED_FROZEN_PATHS
    for item in record["SOURCE_REVISIONS"]:
        assert item["before_sha256"] == frozen[item["path"]]["sha256"]
        assert item["after_sha256"] != item["before_sha256"]


def test_old_single_count_is_rejected_before_any_certificate_recomputation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with monkeypatch.context() as context:
        context.setattr(repair, "SINGLE_TICKET_OUTCOMES", 18_221_078)
        with pytest.raises(AssertionError, match="cross-invariant"):
            repair.build_authority_record()
    assert repair.SINGLE_TICKET_OUTCOMES == 18_611_432
