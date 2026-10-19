"""Eight checks for the split-cap chase of the current minimum-S2 family owners."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import replace

import pytest

from lottolab.research import b649_k20_min_s2_split_cap_current_owner_chase_r1 as x

OWNERS = x.START_OWNER_IDS
NEXT = ["66666555554421000000", "66665555555322000000"]
STOPPER = "66666555555311100000"
TOP_CAPS = {
    "66666665444331000000": 247, "66666664444440000000": 261,
    "66666655544430000000": 261, "66666655544421000000": 252,
    "66666655444440000000": 260, "66666555555330000000": 261,
    "66666555555321000000": 251, "66666555554430000000": 260,
    "66666555544440000000": 259, "66665555555520000000": 261,
    "66665555555511000000": 256, "66665555555430000000": 259,
}  # fmt: skip


@pytest.fixture(scope="module")
def authority() -> x.Authority:
    return x.load_authority()


@pytest.fixture(scope="module")
def derived(authority: x.Authority) -> dict[str, object]:
    return x.compute_result(authority)


def certificate(result: Mapping[str, object], pid: str) -> dict[str, object]:
    certs = map(x.object_row, x.rows(result["CERTIFICATES"]))
    return next(c for c in certs if c["PROFILE_ID"] == pid)


def test_both_start_owners_certified_at_cap_258(derived: dict[str, object]) -> None:
    assert derived["START_FAMILY_BOUND"] == 313_404_784 and derived["START_OWNER_IDS"] == OWNERS
    assert derived["START_OWNERS_CERTIFIED"] is True
    assert derived["START_OWNER_NEW_CAPS"] == dict.fromkeys(OWNERS, 258)
    assert derived["START_OWNER_NEW_BOUNDS"] == dict.fromkeys(OWNERS, 313_351_012)
    for pid, count in zip(OWNERS, (185, 101), strict=True):
        c = certificate(derived, pid)
        assert (c["EXISTING_TRIANGLE_CAP"], c["SPLIT_TRIANGLE_CAP"]) == (264, 258)
        assert x.text(c["EXISTING_AUTHORITY"]).startswith(
            "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES["
        )
        assert c["SPLIT_BRANCH_COUNTS"] == {x.BRANCH_A: count}
        assert x.object_row(c["PREMISES"])["CONDITIONAL_P12_INVOKED"] == "NO"
        degrees = x.object_row(c["DEGREE_DATA"])
        assert (degrees["CORE_COUNT"], degrees["ZERO_COUNT"]) == (13, 7)
        assert x.integer(x.object_row(c["RECORDED_REALIZATION"])["TRIANGLES"]) <= 258


def test_owner_transitions_stop_at_first_untightenable_owner(derived: dict[str, object]) -> None:
    steps = [x.object_row(t) for t in x.rows(derived["OWNER_TRANSITIONS"])]
    assert [(t["FAMILY_BEFORE"], t["OWNER_IDS"], t["FAMILY_AFTER"]) for t in steps] == [
        (313_404_784, OWNERS, 313_404_396),
        (313_404_396, NEXT[:1], 313_404_112),
        (313_404_112, NEXT[1:], 313_404_008),
        (313_404_008, [STOPPER], 313_404_008),
    ]
    assert [t["OWNER_GROUP_COMPLETE"] for t in steps] == [True, True, True, False]
    assert derived["ADDITIONAL_PROFILES_CERTIFIED"] == 2
    assert derived["ADDITIONAL_PROFILE_IDS"] == NEXT
    assert [
        (certificate(derived, p)["TRIANGLE_CAP"], certificate(derived, p)["ALL_T_MAX_BOUND"])
        for p in NEXT
    ] == [(251, 313_287_696), (239, 313_171_100)]
    stopper = certificate(derived, STOPPER)
    assert stopper["STATUS"] == x.NOT_TIGHTENED and stopper["SPLIT_TRIANGLE_CAP"] == 300
    assert stopper["TRIANGLE_CAP"] == stopper["EXISTING_TRIANGLE_CAP"] == 264
    assert derived["STOP"] == {
        "REASON": x.STOP_UNTIGHTENABLE,
        "FAMILY": 313_404_008,
        "OWNER_IDS": [STOPPER],
        "BLOCKING_OWNER_IDS": [STOPPER],
    }
    assert derived["FINAL_COMPLETE_FAMILY_UB"] == 313_404_008
    assert derived["FINAL_OWNER_IDS"] == [STOPPER]
    assert derived["NEXT_COMPETING_BOUND"] == 313_402_304
    assert derived["REMAINING_GAP"] == 140_120 and derived["PROFILES_EVALUATED"] == 5


def test_partial_tied_group_never_lowers_the_family(authority: x.Authority) -> None:
    tied = ["66665555555411100000", "66665555555331000000"]
    out = x.chase({p: authority.ledger[p] for p in tied}, float("inf"))
    assert [c["STATUS"] for c in out.certificates] == [x.NOT_TIGHTENED, x.TIGHTENED]
    assert out.transitions[0]["OWNER_GROUP_COMPLETE"] is False
    assert out.transitions[0]["FAMILY_AFTER"] == out.transitions[0]["FAMILY_BEFORE"] == 313_398_144
    assert out.stop == {
        "REASON": x.STOP_UNTIGHTENABLE,
        "FAMILY": 313_398_144,
        "OWNER_IDS": tied[:1],
        "BLOCKING_OWNER_IDS": tied[:1],
    }
    assert out.ledger[tied[1]].bound == 313_218_904


def test_cursor_split_top_and_budget_stops(
    authority: x.Authority, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = x.chase({OWNERS[0]: authority.ledger[OWNERS[0]]}, float("inf"))
    cursor = [x.prior.CURSOR_ID]
    assert out.stop == {
        "REASON": x.STOP_CURSOR,
        "FAMILY": x.prior.CURSOR_BOUND,
        "OWNER_IDS": cursor,
    }
    top = {x.split.TOP: replace(authority.ledger[x.split.TOP], bound=313_500_000)}
    assert x.chase(top, float("inf")).stop["REASON"] == x.STOP_ALREADY_SPLIT
    assert x.chase(authority.ledger, -1.0).stop["REASON"] == x.STOP_CPU
    monkeypatch.setattr(x, "MAX_REFINED", 3)
    out = x.chase(authority.ledger, float("inf"))
    assert out.stop["REASON"] == x.STOP_BUDGET and len(out.certificates) == 3


def test_p2_accepted_and_conditional_branch_refused(
    authority: x.Authority, derived: dict[str, object]
) -> None:
    soundness = x.object_row(derived["WITNESS_SOUNDNESS"])
    p2 = x.object_row(soundness["P2_COUNTEREXAMPLE"])
    assert (p2["TRIANGLES"], p2["P_TOTAL"], p2["BRANCH"]) == (250, 2, x.BRANCH_A)
    assert derived["UNCONDITIONAL_P12_ASSERTED"] is False
    for c in map(x.object_row, x.rows(derived["CERTIFICATES"])):
        assert set(x.object_row(c["SPLIT_BRANCH_COUNTS"])) == {x.BRANCH_A}
    with pytest.raises(AssertionError, match="conditional P12"):
        x.refine(x.split.SPECIAL, authority.ledger[x.split.SPECIAL])


def test_sts13_witness_kept_and_top_w12_unchanged(derived: dict[str, object]) -> None:
    sts = x.object_row(x.object_row(derived["WITNESS_SOUNDNESS"])["STS13_WITNESS"])
    assert sts["PROFILE_ID"] == "55555555555511111100" and sts["TRIANGLES"] == 270
    assert (sts["LEDGER_TRIANGLE_CAP"], sts["SPLIT_TRIANGLE_CAP"]) == (270, 276)
    assert sts["LEDGER_BOUND"] == 313_402_304
    top = x.object_row(derived["TOP_W12"])
    assert top["STATUS"] == "UNCHANGED" and top["TOPW12_MAX"] == 313_387_144
    assert top["CAPS"] == TOP_CAPS


def test_every_integer_term_reuses_the_existing_envelope(derived: dict[str, object]) -> None:
    certs = [x.object_row(raw) for raw in x.rows(derived["CERTIFICATES"])]
    for c in certs:
        p = x.split.profile_values(x.text(c["PROFILE_ID"]))
        cap, base = x.integer(c["TRIANGLE_CAP"]), x.integer(c["S4_BASE"])
        terms = x.rows(c["ALL_T_TERMS"])
        assert [x.rows(term)[0] for term in terms] == list(range(22, cap + 1))
        assert terms == [list(term) for term in x.split.route_b_terms(p, cap, base)]
        assert c["ALL_T_MAX_BOUND"] == max(x.integer(x.rows(term)[1]) for term in terms)
        old = x.split.route_b_terms(p, x.integer(c["EXISTING_TRIANGLE_CAP"]), base)
        assert max(term[1] for term in old) == c["EXISTING_BOUND"]
        assert terms == [list(term) for term in old[: len(terms)]]
    assert derived["ALL_T_INTEGER_TERMS_CHECKED"] == sum(x.integer(c["TERM_COUNT"]) for c in certs)
    assert derived["ALL_T_INTEGER_TERMS_CHECKED"] == 1165


def test_complete_coverage_recompute_tampering_and_replay(
    authority: x.Authority, derived: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    covered = x.object_row(derived["COVERAGE"])
    assert covered["ADMISSIBLE_PROFILE_COUNT"] == 4844 and covered["UNCOVERED_PROFILE_COUNT"] == 0
    assert (covered["RESOLVED_ROW_COUNT"], covered["UNDER_CURSOR_PROFILE_COUNT"]) == (4647, 197)
    row = authority.ledger[OWNERS[0]]
    with pytest.raises(AssertionError, match="does not reproduce"):
        x.refine(OWNERS[0], replace(row, bound=row.bound - 1))
    members = dict(authority.members)
    members[x.prior.PART_TOP] = frozenset(list(members[x.prior.PART_TOP])[1:])
    with pytest.raises(AssertionError, match="inherited partition"):
        x.coverage(authority.ledger, members, authority.base)
    smaller = dict(authority.ledger)
    del smaller[STOPPER]
    with pytest.raises(AssertionError, match="coverage changed"):
        x.coverage(smaller, authority.members, authority.base)
    outcome = x.chase(smaller, float("inf"))
    with pytest.raises(AssertionError, match="recomputation disagrees"):
        x.final_family(outcome.ledger, outcome)
    base = copy.deepcopy(authority.base)
    base["TOPW12_MAX"] = 313_387_143
    with pytest.raises(AssertionError, match="top-W result changed"):
        x.top_rows(base)
    monkeypatch.setattr(x, "BASE_RESULT_SHA256", "0" * 64)
    with pytest.raises(AssertionError, match="digest mismatch"):
        x.pinned_authority()
    assert x.RESULT_PATH.read_text(encoding="utf-8") == x.render(derived)
