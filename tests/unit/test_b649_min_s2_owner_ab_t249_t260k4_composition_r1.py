"""Focused full-replay and production-path malformed-authority tests."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from typing import cast

import pytest

from lottolab.research import b649_min_s2_owner_ab_t249_t260k4_composition_r1 as m


@pytest.fixture(scope="module")
def authorities() -> tuple[m.Document, list[m.Document]]:
    return m.load_base(), [m.load_donor(pin) for pin in m.DONORS]


@pytest.fixture(scope="module")
def result() -> m.Document:
    return m.compute_result()


def test_complete_sealed_authority(result: m.Document) -> None:
    assert m.render(result) == m.working(m.RESULT)
    assert json.loads(m.working(m.RESULT)) == result
    rows = m.ledger(result["RESOLVED_ROW_BOUNDS"])
    base = m.load_base()
    original = m.ledger(base["RESOLVED_ROW_BOUNDS"])
    assert len(rows) == 4647
    assert {p for p in rows if rows[p] != original[p]} == {m.A, m.B}
    assert sum(rows[p] == original[p] for p in rows) == 4645
    assert rows[m.A] == 313248348 and rows[m.B] == 313345152
    assert result["CURSOR"] == base["CURSOR"]
    assert result["FAMILY_DELTA"] == 104
    scenarios = m.obj(result["SCENARIOS"])
    assert [
        m.obj(scenarios[label])["FAMILY_BOUND"]
        for label in ("S0_BASE", "S1_OWNER_A_ONLY", "S2_OWNER_B_ONLY", "S3_BOTH")
    ] == [313391740, 313391740, 313391740, 313391636]
    assert m.obj(scenarios["S0_BASE"])["OWNER_IDS"] == [m.A, m.B]
    assert m.obj(scenarios["S1_OWNER_A_ONLY"])["OWNER_IDS"] == [m.B]
    assert m.obj(scenarios["S2_OWNER_B_ONLY"])["OWNER_IDS"] == [m.A]
    final = m.obj(result["FAMILY_AFTER"])
    assert final["OWNER_IDS"] == ["66665555555321100000"]
    assert final["GAP_TO_INCUMBENT"] == 127748
    assert final["STILL_OPEN_PROFILE_COUNT"] == 1515
    assert m.obj(scenarios["S0_BASE"])["STILL_OPEN_PROFILE_COUNT"] == 1516
    assert m.obj(scenarios["S1_OWNER_A_ONLY"])["STILL_OPEN_PROFILE_COUNT"] == 1515
    assert m.obj(scenarios["S2_OWNER_B_ONLY"])["STILL_OPEN_PROFILE_COUNT"] == 1516


def test_full_envelopes(authorities: tuple[m.Document, list[m.Document]]) -> None:
    _, donors = authorities
    for pin, doc in zip(m.DONORS, donors, strict=True):
        cert = m.verify_certificate(pin, doc)
        envelope = cast(list[m.Document], cert["TERMS"])
        assert [term["T"] for term in envelope] == list(range(22, pin.cap + 1))
        assert len(envelope) == (228 if pin.profile == m.A else 239)
        assert m.maximum(envelope) == pin.bound
    assert len(m.terms(m.A, 265, 197)) == 244
    assert m.maximum(m.terms(m.B, 260, 197)) == 313346736
    assert m.maximum(m.terms(m.B, 265, 185)) == 313390156
    assert m.maximum(m.terms(m.B, 260, 185)) == 313345152


@pytest.mark.parametrize(
    "case",
    [
        "a_profile",
        "b_profile",
        "swap_bounds",
        "a_cap",
        "b_cap",
        "b_k4_cap",
        "a_missing_term",
        "b_missing_term",
        "a_s4_scope",
        "b_s4_scope",
        "b_s4_formula",
        "s5",
        "b_weaker_bound",
        "b_t265_bound",
        "a_old_missing_term",
        "b_t_domain_shift",
    ],
)
def test_reject_donor_corruption(
    authorities: tuple[m.Document, list[m.Document]],
    case: str,
) -> None:
    base, originals = authorities
    donors = copy.deepcopy(originals)
    a, b = donors
    if case == "a_profile":
        m.obj(a["FACTS"])["PROFILE"] = m.B
    elif case == "b_profile":
        b["TARGET_PROFILE"] = m.A
    elif case == "swap_bounds":
        a["NEW_FULL_PROFILE_BOUND"], b["NEW_FULL_PROFILE_BOUND"] = (
            b["NEW_FULL_PROFILE_BOUND"],
            a["NEW_FULL_PROFILE_BOUND"],
        )
    elif case in ("a_cap", "b_cap"):
        (a if case == "a_cap" else b)["NEW_PROVEN_T_CAP"] = 265
    elif case == "b_k4_cap":
        m.obj(b["K4_CERTIFICATE"])["CAP"] = 197
    elif case in ("a_missing_term", "a_old_missing_term"):
        cast(list[object], a["NEW_T_TERMS" if case == "a_missing_term" else "OLD_T_TERMS"]).pop(80)
    elif case == "b_missing_term":
        cast(list[object], b["T_TERMS"]).pop(90)
    elif case == "a_s4_scope":
        cast(list[list[int]], a["NEW_T_TERMS"])[0][4] = 212513
    elif case == "b_s4_scope":
        cast(list[m.Document], b["T_TERMS"])[0]["S4"] = 271642
    elif case == "b_s4_formula":
        b["NEW_PROVEN_S4"] = "MAX(112,679*q-231*MIN(q,197))"
    elif case == "s5":
        a["NEW_PROVEN_S5"] = "ADOPTED"
    elif case in ("b_weaker_bound", "b_t265_bound"):
        b["NEW_FULL_PROFILE_BOUND"] = 313346736 if case == "b_weaker_bound" else 313390156
    else:
        cast(list[m.Document], b["T_TERMS"])[0]["T"] = 21
    with pytest.raises(ValueError):
        m.compose(base, donors)


@pytest.mark.parametrize("path_kind", ["source", "test", "result", "tree", "judge"])
def test_reject_immutable_identity_mismatch(
    monkeypatch: pytest.MonkeyPatch, path_kind: str
) -> None:
    original: Callable[..., bytes] = m.git
    pin = m.DONORS[0]

    def corrupt(*args: str) -> bytes:
        raw = original(*args)
        if args[0] == "cat-file":
            path = args[-1]
            selected = (
                path.endswith(f"/{pin.stem}.py")
                if path_kind == "source"
                else path.endswith(f"/test_{pin.stem}.py")
                if path_kind == "test"
                else path.endswith("-result.json")
                if path_kind == "result"
                else False
            )
            if selected:
                return raw + b" "
        if path_kind == "tree" and args[0] == "rev-parse":
            return b"0" * 40
        if path_kind == "judge" and args[0] == "show":
            return raw.replace(pin.sealed_report_sha.encode(), b"0" * 64)
        return raw

    monkeypatch.setattr(m, "git", corrupt)
    with pytest.raises(ValueError):
        m.load_donor(pin)


@pytest.mark.parametrize("case", ["missing_row", "cursor_id", "cursor_bound", "cursor_coverage"])
def test_reject_incomplete_replay(
    authorities: tuple[m.Document, list[m.Document]],
    case: str,
) -> None:
    base = copy.deepcopy(authorities[0])
    cursor = m.obj(base["CURSOR"])
    if case == "missing_row":
        m.obj(base["RESOLVED_ROW_BOUNDS"]).pop(next(iter(m.obj(base["RESOLVED_ROW_BOUNDS"]))))
    elif case == "cursor_id":
        cast(list[str], cursor["PROFILE_IDS"])[0] = m.A
    elif case == "cursor_bound":
        projection = m.obj(cursor["COARSE_BOUND_PROJECTION"])
        projection[next(iter(projection))] = 313391636
    else:
        cursor["PARTITION"] = {"WRONGLY_REPLACED": True}
    with pytest.raises(ValueError, match="immutable Base"):
        m.replay(base, ((m.A, m.DONORS[0].bound), (m.B, m.DONORS[1].bound)))


@pytest.mark.parametrize(
    "updates",
    [
        ((m.A, 313248348), (m.A, 313248348)),
        ((m.A, 313345152), (m.B, 313248348)),
        (("66665555555321100000", 313248348),),
    ],
)
def test_reject_duplicate_or_unauthorized_updates(
    authorities: tuple[m.Document, list[m.Document]],
    updates: tuple[tuple[str, int], ...],
) -> None:
    with pytest.raises(ValueError):
        m.replay(authorities[0], updates)


@pytest.mark.parametrize("case", ["false_maximum", "pending_upgrade"])
def test_reject_false_result_or_status_upgrade(result: m.Document, case: str) -> None:
    corrupted = copy.deepcopy(result)
    if case == "false_maximum":
        m.obj(corrupted["FAMILY_AFTER"])["FAMILY_BOUND"] = 313345152
    else:
        inherited = m.obj(corrupted["INHERITED_CAVEATS_AND_STATUS_VERBATIM"])
        m.obj(inherited["OWNER_B"])["HISTORICAL_R15"] = "PASS"
    with pytest.raises(ValueError, match="sealed result"):
        m.verify_result(corrupted)


def test_preserves_whole_disposition_subtrees(
    authorities: tuple[m.Document, list[m.Document]],
    result: m.Document,
) -> None:
    base, donors = authorities
    inherited = m.obj(result["INHERITED_CAVEATS_AND_STATUS_VERBATIM"])
    for name, original in (("BASE", base), ("OWNER_A", donors[0]), ("OWNER_B", donors[1])):
        assert inherited[name] == m.dispositions(original)
    pending: m.Document = {
        "INHERITED_CAVEATS": {"DONOR": {"STATUS": "PENDING", "JUDGE": "SELF_CHECK_ONLY"}}
    }
    assert m.dispositions(pending) == pending
    assert result["LEGAL_ATTAINMENT"] == result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["HISTORICAL_R15"] == "NOT_VERIFIED"
