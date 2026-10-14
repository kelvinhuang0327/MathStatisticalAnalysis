"""Focused coverage, universality, exact envelope, family and negative gates (41 cursors)."""

from __future__ import annotations

import random
from collections.abc import Iterator
from copy import deepcopy
from fractions import Fraction
from itertools import combinations, combinations_with_replacement
from math import comb
from typing import cast

import pytest

# Keep bootstrap first so certificate imports resolve from the pinned source snapshot.
# isort: off
from tests.unit.b649_certificate_replay import replay_certificate_call, replay_fixed_result
from lottolab.research import b649_cursor_41_owner_shared_bound_r1 as cert
# isort: on

S1_MINUS_S2 = 372_228_640 - 63_838_600
TOP_EIGHT = [
    "44444444444443332210",
    "44444444444444222220",
    "54444444444333333210",
    "54444444444433322220",
    "54444444444433332111",
    "55444444433333333310",
    "55444444443333332220",
    "64444444433333333220",
]


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return replay_fixed_result(cert.__name__)


@pytest.fixture
def owner_cache() -> Iterator[None]:
    cert.owner_ids.cache_clear()
    yield
    cert.owner_ids.cache_clear()


def histograms() -> dict[str, int]:
    # Independent of cert.raw_histograms: multisets, not a descending recursion.
    out: dict[str, int] = {}
    for combo in combinations_with_replacement(range(7), 20):
        if sum(combo) == 66:
            out["".join(map(str, sorted(combo, reverse=True)))] = sum(comb(6 + v, 2) for v in combo)
    return out


def own_term(d: tuple[int, ...], t: int, floor: int) -> tuple[int, int, int, int, int, int]:
    g = [6 + v for v in d]
    w = sum(comb(v, 2) for v in g)
    o = w - 3 * t
    k4 = max(0, -(-(sum(comb(v, 3) for v in g) - (max(g) - 2) * o) // 4))
    a = min(k4, sum(v * (v + 4) for v in d) // 3)
    s4 = max(floor, 448 * a + 679 * (k4 - a))
    s3 = 2800 * o + 20272 * (t - 22) + 154000
    exact = S1_MINUS_S2 + s3 - Fraction(4 * s4, 7)
    return t, -(-exact.numerator // exact.denominator), k4, a, s4, s3


def test_coverage_is_exactly_every_w785_histogram(result: dict[str, object]) -> None:
    raw = histograms()
    assert len(raw) == 5126 and min(raw.values()) == 774
    cursor = cert.obj(result["CURSOR"])
    ids = cast(list[str], cursor["PROFILE_IDS"])
    assert sorted(ids) == sorted(p for p, w in raw.items() if w <= 785) and len(ids) == 197
    owners = cast(list[str], result["OWNER_IDS"])
    assert sorted(owners) == sorted(p for p, w in raw.items() if w == 785) and len(owners) == 41
    assert cursor["ID"] in owners and cursor["BOUND"] == 313394584
    resolved = cast(dict[str, int], result["RESOLVED_ROW_BOUNDS"])
    assert min(raw[p] for p in resolved) == 786 and not set(resolved) & set(ids)
    assert cert.obj(result["CURSOR_COVERAGE"])["R18_R30_CAPS_OR_STATUSES_USED"] == 0


def test_universal_wedge_and_k4_floor_on_random_graphs() -> None:
    rng = random.Random(20261014)
    for _ in range(400):
        n = rng.randint(5, 10)
        edges = {e for e in combinations(range(n), 2) if rng.random() < rng.random()}
        adj = [{v for e in edges if u in e for v in e if v != u} for u in range(n)]
        g = [len(a) for a in adj]
        t = sum(set(combinations(q, 2)) <= edges for q in combinations(range(n), 3))
        k4 = sum(set(combinations(q, 2)) <= edges for q in combinations(range(n), 4))
        w = sum(comb(v, 2) for v in g)
        assert 3 * t <= w
        assert 4 * k4 >= sum(comb(v, 3) for v in g) - max(0, max(g) - 2) * (w - 3 * t)


def test_contained_triple_k4_cap_on_random_pair_linear_configurations() -> None:
    rng = random.Random(785)
    for _ in range(300):
        n = rng.randint(6, 11)
        triples: list[tuple[int, int, int]] = []
        used: set[tuple[int, int]] = set()
        for q in rng.sample(list(combinations(range(n), 3)), k=min(12, comb(n, 3))):
            pairs = set(combinations(q, 2))
            if not pairs & used and rng.random() < 0.6:
                triples.append(q)
                used |= pairs
        free = [e for e in combinations(range(n), 2) if e not in used]
        edges = used | {e for e in free if rng.random() < 0.5}
        g = [sum(v in e for e in edges) for v in range(n)]
        d = [sum(v in q for q in triples) for v in range(n)]
        k4s = [q for q in combinations(range(n), 4) if set(combinations(q, 2)) <= edges]
        assert all(sum(set(s) <= set(q) for s in triples) <= 1 for q in k4s)
        contained = sum(any(set(s) <= set(q) for s in triples) for q in k4s)
        assert contained <= sum(dv * (gv - 2) for dv, gv in zip(d, g, strict=True)) // 3


def test_inherited_quartet_weights_and_s3_identity() -> None:
    assert cert.route.K4_WEIGHTS == {
        cert.route.WITH_TRIPLE: 448,
        cert.route.WITHOUT_TRIPLE: 679,
    }
    assert cert.route.r30.k4_quartet_weights() == cert.route.K4_WEIGHTS
    for t in range(22, 262):
        own = 2800 * (785 - 3 * t) + 20272 * (t - 22) + 154000
        assert own == cert.route.bound_from_cap(tuple(map(int, TOP_EIGHT[0])), t, 0)[0]


def test_coarse_bound_is_the_same_formula_at_top_t_with_floor_only(
    result: dict[str, object],
) -> None:
    for pid in cast(list[str], result["OWNER_IDS"]):
        exact = S1_MINUS_S2 + 2800 * 2 + 20272 * 239 + 154000 - Fraction(4 * 112, 7)
        assert (
            exact
            == 313394584
            == cert.route.r28.coarse_profile_envelope(tuple(map(int, pid))).family_upper_bound
        )


def test_every_term_of_all_41_envelopes_recomputed_independently(
    result: dict[str, object],
) -> None:
    per = cert.obj(result["PER_CURSOR"])
    assert len(per) == 41
    for pid, raw in per.items():
        row = cert.obj(raw)
        d = tuple(map(int, pid))
        own = [own_term(d, t, 112) for t in range(22, 262)]
        assert row["ALL_T_TERMS_SHA256"] == cert.sha(cert.render(own))
        new = max(t[1] for t in own)
        assert new == max(own_term(d, t, 0)[1] for t in range(22, 262)) == row["NEW_BOUND"]
        assert all(own[i][1] < own[i + 1][1] for i in range(len(own) - 1))
        argmax = [tuple(t) for t in cast(list[list[int]], row["ALL_ARGMAX"])]
        assert argmax == [own[-1]] and row["OLD_COARSE_BOUND"] == 313394584
        assert row["DELTA"] == 313394584 - new > 0 and row["A_MAX"] == 169


def test_per_cursor_old_new_bounds_and_shared_class(result: dict[str, object]) -> None:
    per = {
        p: cert.integer(cert.obj(v)["NEW_BOUND"]) for p, v in cert.obj(result["PER_CURSOR"]).items()
    }
    assert max(per.values()) == result["NEW_OWNER_MAXIMUM"] == 313226448
    assert result["NEW_OWNER_MAXIMUM_IDS"] == TOP_EIGHT
    assert per["66544333333333332222"] == min(per.values()) == 313225284
    assert sorted(set(per.values())) == [313225284, 313225672, 313226060, 313226448]
    shared = cert.obj(result["CLASS_ENVELOPE"])
    assert shared["BOUND"] == 313226836 and shared["SUM_C_G_3_FLOOR"] == 1979
    assert result["ALL_41_STRICTLY_BELOW_OLD"] is True
    assert result["FRACTIONAL_S4_CREDIT_TERMS"] == 0


@pytest.mark.parametrize(
    "floor,top,members,message",
    [
        (1980, 12, None, "class C3 floor"),
        (1979, 11, None, "class g_max"),
        (1979, 13, None, "class g_max"),
        (1979, 12, slice(1, None), "exactly the 41"),
    ],
)
def test_wrong_class_assumptions_rejected(
    result: dict[str, object], floor: int, top: int, members: slice | None, message: str
) -> None:
    owners = cast(list[str], result["OWNER_IDS"])
    with pytest.raises(ValueError, match=message):
        cert.class_envelope(owners if members is None else owners[members], floor, top)


@pytest.mark.parametrize(
    "pid",
    [
        "44444444444433333210",  # W=784 cursor, not an owner.
        "65555555555541000000",  # Resolved family owner after this task.
        "66555555555431100000",  # Previous single-owner target.
        "01244444444443332244",  # Unsorted copy of an owner's digits.
        "",
    ],
)
def test_wrong_cursor_identity_rejected(pid: str) -> None:
    with pytest.raises(ValueError, match="not one of the 41"):
        cert.theorem(pid)


def test_wrong_coverage_relation_rejected(result: dict[str, object]) -> None:
    ids = cast(list[str], cert.obj(result["CURSOR"])["PROFILE_IDS"])
    owners = cast(list[str], result["OWNER_IDS"])
    resolved = list(cast(dict[str, int], result["RESOLVED_ROW_BOUNDS"]))
    with pytest.raises(ValueError, match="cursor ID count"):
        cert.coverage(ids[1:], owners, resolved)
    with pytest.raises(ValueError, match="not exactly the W<=785"):
        cert.coverage([*ids[1:], resolved[0]], owners, resolved)
    with pytest.raises(ValueError, match="owner ID count"):
        cert.coverage(ids, owners[1:], resolved)
    w784 = next(p for p in ids if cert.wedges(tuple(map(int, p))) == 784)
    with pytest.raises(ValueError, match="not exactly the W=785"):
        cert.coverage(ids, [*owners[1:], w784], resolved)
    with pytest.raises(ValueError, match="inside the cursor band"):
        cert.coverage(ids, owners, [*resolved, owners[0]])


@pytest.mark.parametrize("cap", [260, 255, 262, True])
def test_non_universal_cap_rejected(result: dict[str, object], cap: int) -> None:
    pid = TOP_EIGHT[0]
    terms = [own_term(tuple(map(int, pid)), t, 112) for t in range(22, 262)]
    with pytest.raises(ValueError, match=r"universal wedge cap|owner/cap"):
        cert.validate_envelope(pid, cap, 112, terms)


def test_missing_term_and_wrong_rounding_rejected() -> None:
    pid = TOP_EIGHT[0]
    terms = cert.envelope(pid, 112)
    for omitted in (0, 120, len(terms) - 1):
        with pytest.raises(ValueError, match="incomplete T envelope"):
            cert.validate_envelope(pid, 261, 112, terms[:omitted] + terms[omitted + 1 :])
    # Every certified credit here is integral (all S4 are multiples of 7): probe with floor 113.
    probe = cert.envelope(pid, 113)
    first = probe[0]
    exact = S1_MINUS_S2 + first[5] - Fraction(4 * first[4], 7)
    assert first[4] == 113 and exact.denominator == 7 and first[1] == exact.numerator // 7 + 1
    floored = [(*first[:1], exact.numerator // 7, *first[2:]), *probe[1:]]
    with pytest.raises(ValueError, match="final ceiling rounding"):
        cert.validate_envelope(pid, 261, 113, floored)
    at = len(terms) - 1
    row = terms[at]
    assert row[2] > row[3] == 169
    for index, value, message in (
        (1, row[1] - 1, "final ceiling rounding"),
        (2, row[2] - 1, "K4 rounding"),
        (2, row[2] + 1, "K4 rounding"),
        (3, row[3] - 1, "A_max containment"),
        (4, row[4] + 112, "S4 direction"),
        (5, row[5] + 1, "S3 identity"),
    ):
        changed = list(terms)
        changed[at] = cast(cert.Term, (*row[:index], value, *row[index + 1 :]))
        with pytest.raises(ValueError, match=message):
            cert.validate_envelope(pid, 261, 112, changed)


def test_partial_or_non_strict_tightening_never_claims_gain(result: dict[str, object]) -> None:
    coarse = cast(dict[str, int], result["CURSOR_ROW_BOUNDS_BEFORE"])
    resolved = cast(dict[str, int], result["RESOLVED_ROW_BOUNDS"])
    per = {
        p: cert.integer(cert.obj(v)["NEW_BOUND"]) for p, v in cert.obj(result["PER_CURSOR"]).items()
    }
    before = cert.prev.family(resolved, coarse)
    for dropped in per:
        partial = {p: b for p, b in per.items() if p != dropped}
        with pytest.raises(ValueError, match="not exactly the owners"):
            cert.tightened(coarse, partial)
        forced = coarse | partial
        after = cert.prev.family(resolved, forced)
        assert after["MAXIMUM"] == 313394584 and after["ALL_MAX_OWNERS"] == [dropped]
        assert cert.family_status(before, after, partial) == "NO_PROVEN_FAMILY_GAIN"
    with pytest.raises(ValueError, match="non-strict"):
        cert.tightened(coarse, per | {TOP_EIGHT[0]: 313394584})
    with pytest.raises(ValueError, match="not exactly the owners"):
        cert.tightened(coarse, per | {"44444444444433333210": 1})


def test_deleted_cursor_and_wrong_aggregation_rejected(result: dict[str, object]) -> None:
    after = cast(dict[str, int], result["CURSOR_ROW_BOUNDS_AFTER"])
    resolved = cast(dict[str, int], result["RESOLVED_ROW_BOUNDS"])
    for victim in (TOP_EIGHT[0], "44444433333333333333"):
        with pytest.raises(ValueError, match="row count"):
            cert.prev.family(resolved, {p: b for p, b in after.items() if p != victim})
    with pytest.raises(ValueError, match="row count"):
        cert.prev.family(dict(list(resolved.items())[1:]), after)
    with pytest.raises(ValueError, match="cursor row count"):
        cert.tightened(dict(list(after.items())[1:]), {})
    merged = resolved | after
    levels = sorted(set(merged.values()), reverse=True)
    assert levels[:2] == [313392516, 313392412]
    assert max(after.values()) == 313391784 != levels[0]  # A cursor-only maximum is wrong.


def test_source_identity_drift_rejected(monkeypatch: pytest.MonkeyPatch, owner_cache: None) -> None:
    original = cert.r2.git

    def damaged(*args: str) -> bytes:
        raw = original(*args)
        return raw + b"\n" if args[0] == "show" and args[1].endswith(cert.INPUT_RESULT) else raw

    with pytest.raises(ValueError, match="tree pin"):
        cert.identity(cert.INPUT_HEAD, cert.TWO_OWNER_TREE)
    monkeypatch.setattr(cert.r2, "git", damaged)
    with pytest.raises(ValueError, match="blob pin"):
        cert.fixed_input()
    monkeypatch.undo()
    cert.owner_ids.cache_clear()
    monkeypatch.setattr(cert, "OWNER_IDS_SHA256", "0" * 64)
    with pytest.raises(ValueError, match="owner pin"):
        cert.owner_ids()


def test_no_r30_status_names_any_cursor_row(result: dict[str, object]) -> None:
    r30 = cert.decode(cert.blob(cert.BASE_HEAD, cert.r2.R30_PATH, cert.r2.R30_SHA))
    ids = set(cast(list[str], cert.obj(result["CURSOR"])["PROFILE_IDS"]))
    attempts = cast(list[dict[str, object]], r30["GROUP_ATTEMPTS"])
    assert all(not set(cast(list[str], a.get("PROFILE_IDS", []))) & ids for a in attempts)


@pytest.mark.parametrize("field,value", [("FAMILY_AFTER", 313394584), ("TASK_STATUS", "X")])
def test_tampered_result_rejected(result: dict[str, object], field: str, value: object) -> None:
    changed = deepcopy(result)
    changed[field] = value
    with pytest.raises(ValueError, match="not exactly reproducible"):
        replay_certificate_call(cert.__name__, "verify_result", changed)


def test_family_recompute_and_no_authority_inflation(result: dict[str, object]) -> None:
    assert cert.RESULT.read_bytes() == cert.render(result)
    assert result["TASK_STATUS"] == "PROVEN_FAMILY_GAIN"
    before = cast(dict[str, int], result["CURSOR_ROW_BOUNDS_BEFORE"])
    after = cast(dict[str, int], result["CURSOR_ROW_BOUNDS_AFTER"])
    owners = set(cast(list[str], result["OWNER_IDS"]))
    assert len(before) == len(after) == 197 and set(before) == set(after)
    assert {p for p in before if before[p] != after[p]} == owners
    assert result["OTHER_CURSOR_ROWS_UNCHANGED"] == 156
    assert cert.obj(result["CURSOR"])["COARSE_BOUND_PROJECTION"] == before
    resolved = cast(dict[str, int], result["RESOLVED_ROW_BOUNDS"])
    fixed = cert.decode(
        cert.blob(cert.INPUT_HEAD, cert.INPUT_RESULT, cert.INPUT_PINS[cert.INPUT_RESULT])
    )
    assert resolved == fixed["RESOLVED_ROW_BOUNDS_AFTER"] and len(resolved) == 4647
    assert result["FAMILY_BEFORE"] == 313394584 and result["FAMILY_AFTER"] == 313392516
    assert result["FAMILY_DELTA"] == 2068 and result["GAP_TO_INCUMBENT"] == 128628
    assert result["ALL_NEW_MAX_OWNERS"] == ["65555555555541000000"]
    assert result["NEXT_DISTINCT_BOUND"] == 313392412
    assert cert.obj(result["PROJECTED_FAMILY_AFTER"])["MAXIMUM_OWNER_CLASSES"] == ["RESOLVED"]
    assert result["GLOBAL_OPTIMUM"] == "UNKNOWN" and result["PREDICTION_GAIN_CLAIMED"] is False
    assert result["CANONICAL_AUTHORITY_CHANGED"] == result["REMOTE_WRITE"] == "NO"
    assert result["PRODUCTION_MUTATION"] == "NONE" and result["S5_USED"] is False
    assert result["SOLVER_CALLS"] == result["PORTFOLIOS_ENUMERATED"] == 0
    assert len(cert.obj(result["SOURCE_PINS"])) == 22
