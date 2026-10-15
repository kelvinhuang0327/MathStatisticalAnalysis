"""Acceptance and injected defects on the production compute_result path."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Mapping, Sequence
from fractions import Fraction
from typing import cast

import pytest

from lottolab.research import b649_min_s2_w784_39_goodman_exact_authority_r1 as authority


@pytest.fixture(scope="module")
def result() -> authority.Document:
    return authority.compute_result()


def test_goodman_complete_cohort_and_exact_arithmetic(result: authority.Document) -> None:
    ids = cast(list[str], result["COHORT_IDS"])
    assert len(ids) == 39 and ids == sorted(set(ids), reverse=True)
    assert result["COHORT_IDS_SHA256"] == authority.IDS_SHA
    assert result["UNIVERSAL_T_CAP"] == 250
    assert result["COHORT_BOUND_BEFORE"] == 313391784
    assert result["COHORT_BOUND_AFTER"] == 313261192
    assert result["COHORT_DELTA"] == 130592
    for value in authority.obj(result["PROFILE_CERTIFICATES"]).values():
        proof = authority.obj(value)
        facts = authority.obj(proof["FACTS"])
        assert (facts["N"], facts["E"], facts["SUM_G"], facts["SUM_G_SQUARED"], facts["W"]) == (
            20,
            93,
            186,
            1754,
            784,
        )
        assert facts["MIXED_ORDERED"] == 1780
        terms = cast(list[int], proof["ALL_T_INTEGER_BOUNDS"])
        assert len(terms) == 229 and max(terms) == terms[-1] == 313261192
    assert authority.obj(result["EXACT_ARITHMETIC"])["S5_USED"] is False


def test_full_family_replay_and_unchanged_authority(result: authority.Document) -> None:
    base = authority.load_base()
    rows = authority.ledger(result["RESOLVED_ROW_BOUNDS"])
    assert rows == base["RESOLVED_ROW_BOUNDS"] and len(rows) == 4647
    before = authority.obj(base["CURSOR"])
    after = authority.obj(result["CURSOR"])
    before_bounds = authority.ledger(before["COARSE_BOUND_PROJECTION"])
    after_bounds = authority.ledger(after["COARSE_BOUND_PROJECTION"])
    assert len(after_bounds) == 197
    changed = sorted(
        (p for p in before_bounds if after_bounds[p] != before_bounds[p]), reverse=True
    )
    assert changed == result["COHORT_IDS"]
    assert sum(after_bounds[p] == b for p, b in before_bounds.items()) == 158
    assert {k: v for k, v in before.items() if k != "COARSE_BOUND_PROJECTION"} == {
        k: v for k, v in after.items() if k != "COARSE_BOUND_PROJECTION"
    }
    family = authority.obj(result["FAMILY_AFTER"])
    assert family["FAMILY_BOUND"] == 313391740
    assert family["OWNER_IDS"] == ["66655555555331100000", "66655555555411110000"]
    assert family["GAP_TO_INCUMBENT"] == 127852
    assert family["STILL_OPEN_PROFILE_COUNT"] == 1516
    assert result["FAMILY_DELTA"] == 44
    assert result["RESOLVED_ROW_BOUNDS_CHANGED"] == 0


def test_caveats_and_donor_disposition_preserved(result: authority.Document) -> None:
    inherited = authority.obj(result["INHERITED_AUTHORITY_VERBATIM"])
    base = authority.load_base()
    assert all(v == base[k] for k, v in inherited.items())
    assert result["HISTORICAL_R15"] == result["EXTERNAL_18526_TERM_REFERENCE"] == "NOT_VERIFIED"
    report = authority.obj(result["BASE_FRESH_JUDGE"])
    caveats = cast(str, report["CAVEATS_VERBATIM"])
    assert all(f"finding_id: F{i}" in caveats for i in range(1, 5))
    prior = authority.obj(result["PRIOR_ART"])
    assert prior["HEAD"] == authority.PRIOR_HEAD and prior["ADOPTED"] is False
    assert prior["FORMAL_ROUTE_B_RECERTIFIED"] is False
    assert result["LEGAL_ATTAINMENT"] == result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["HEAVY_SOLVER_STARTED"] == result["REMOTE_WRITE"] == "NO"
    assert result["ADVANCED_11ROW_RECERTIFIED"] is False


@pytest.mark.parametrize(
    "defect,match",
    [
        ("wrong_cohort", "wrong cohort canonical"),
        ("missing_cursor", "missing cursor/coverage"),
        ("duplicate_update", "duplicate update"),
        ("wrong_w", "wrong W/degree identities"),
        ("incorrect_goodman", "incorrect Goodman cap"),
        ("wrong_sign", "wrong S3 sign"),
        ("wrong_rounding", "wrong rounding"),
        ("source_mismatch", "source mismatch: working evaluator"),
        ("missing_update", "wrong cohort/missing update"),
        ("wrong_update_bound", "incorrect update bound"),
    ],
)
def test_production_entry_rejects_defects(
    defect: str,
    match: str,
    monkeypatch: pytest.MonkeyPatch,
    result: authority.Document,
) -> None:
    ids = cast(list[str], result["COHORT_IDS"])
    if defect == "wrong_cohort":
        cursor_ids = cast(list[str], authority.obj(authority.load_base()["CURSOR"])["PROFILE_IDS"])
        foreign = next(p for p in cursor_ids if p not in ids)

        def foreign_cohort(_: Sequence[str]) -> list[str]:
            return sorted([*ids[1:], foreign], reverse=True)

        monkeypatch.setattr(authority, "derive_cohort", foreign_cohort)
    elif defect == "missing_cursor":
        base = copy.deepcopy(authority.load_base())
        cursor = authority.obj(base["CURSOR"])
        cast(list[str], cursor["PROFILE_IDS"]).pop()
        monkeypatch.setattr(authority, "load_base", lambda: base)
    elif defect in {"duplicate_update", "missing_update", "wrong_update_bound"}:
        original = authority.make_updates

        def bad_updates(profiles: Sequence[str], bound: int) -> list[tuple[str, int]]:
            values = original(profiles, bound)
            if defect == "duplicate_update":
                return [*values, values[0]]
            if defect == "missing_update":
                return values[:-1]
            return [(p, b + 1) for p, b in values]

        monkeypatch.setattr(authority, "make_updates", bad_updates)
    elif defect == "wrong_w":
        original_facts = authority.profile_facts

        def wrong_w(pid: str) -> dict[str, int]:
            facts = original_facts(pid)
            if pid == ids[0]:
                facts["W"] = 785
            return facts

        def frozen_cohort(_: Sequence[str]) -> list[str]:
            return ids

        monkeypatch.setattr(authority, "derive_cohort", frozen_cohort)
        monkeypatch.setattr(authority, "profile_facts", wrong_w)
    elif defect == "incorrect_goodman":

        def bad_goodman(_: Mapping[str, int]) -> int:
            return 251

        monkeypatch.setattr(authority, "goodman_cap", bad_goodman)
    elif defect == "wrong_sign":

        def negative_sign(w: int, t: int) -> int:
            return 2800 * w - 11872 * (t - 22) - 30800

        monkeypatch.setattr(authority, "s3_at", negative_sign)
    elif defect == "wrong_rounding":

        def rounded_down(value: Fraction) -> int:
            return value.numerator // value.denominator

        monkeypatch.setattr(authority, "ceil_fraction", rounded_down)
    else:
        original_bytes = authority.working_bytes

        def altered_bytes(path: str) -> bytes:
            payload = original_bytes(path)
            return payload + b"\n# altered source" if path.endswith("r8.py") else payload

        monkeypatch.setattr(authority, "working_bytes", altered_bytes)
    with pytest.raises(ValueError, match=match):
        authority.compute_result()


@pytest.mark.parametrize("defect", ["missing_resolved", "wrong_s4", "wrong_square_sum"])
def test_other_production_premises(
    defect: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if defect == "missing_resolved":
        base = copy.deepcopy(authority.load_base())
        authority.obj(base["RESOLVED_ROW_BOUNDS"]).popitem()
        monkeypatch.setattr(authority, "load_base", lambda: base)
        match = "missing cursor/coverage"
    elif defect == "wrong_s4":
        monkeypatch.setattr(authority.r8, "INHERITED_S4_LOWER_BOUND", 113)
        match = "inherited S4 scope"
    else:
        original: Callable[[str], dict[str, int]] = authority.profile_facts

        def wrong_square_sum(pid: str) -> dict[str, int]:
            facts = original(pid)
            facts["SUM_G_SQUARED"] += 1
            return facts

        monkeypatch.setattr(authority, "profile_facts", wrong_square_sum)
        match = "wrong W/degree identities"
    with pytest.raises(ValueError, match=match):
        authority.compute_result()


def test_deterministic_result_and_rejection(result: authority.Document) -> None:
    payload = (authority.ROOT / authority.RESULT).read_bytes()
    assert payload == authority.render(result)
    authority.verify_result(json.loads(payload))
    corrupted = copy.deepcopy(result)
    corrupted["UNIVERSAL_T_CAP"] = 251
    with pytest.raises(ValueError, match="deterministic result mismatch"):
        authority.verify_result(corrupted)
