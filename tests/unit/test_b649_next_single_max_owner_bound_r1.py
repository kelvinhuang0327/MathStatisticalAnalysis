"""Focused universal proof, exhaustive small relaxation, exact envelope and pin gates."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from itertools import combinations, product
from math import comb
from typing import cast

import pytest

# Keep bootstrap first so certificate imports resolve from the pinned source snapshot.
# isort: off
from tests.unit.b649_certificate_replay import replay_certificate_call, replay_fixed_result
from lottolab.research import b649_next_single_max_owner_bound_r1 as cert
# isort: on


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return replay_fixed_result(cert.__name__)


def test_exact_profile_facts_independently() -> None:
    facts = cert.theorem()
    d = tuple(int(x) for x in cert.TARGET)
    g = tuple(6 + x for x in d)
    assert Counter(d) == {6: 2, 5: 9, 4: 1, 3: 1, 1: 2, 0: 5}
    assert len(d) == facts["VERTICES"] == 20
    assert sum(d) == facts["DEGREE_SUM_D"] == 66
    assert sum(g) == facts["DEGREE_SUM_G"] == 2 * cert.integer(facts["SUPPORT_EDGES"]) == 186
    assert sum(x * x for x in g) == facts["SUM_G_SQUARED"] == 1836
    assert sum(comb(x, 2) for x in g) == facts["WEDGES"] == 825
    assert comb(20, 3) - Fraction(sum(x * (19 - x) for x in g), 2) == facts["GOODMAN_SUM"] == 291
    assert (20 - d.count(0), d.count(0)) == (facts["K"], facts["Z"]) == (15, 5)
    assert facts["SPLIT_CONSTANT"] == 291 - (5 * 54 + 15 * -10) // 2 == 231
    assert facts["ZETA_RANGE"] == [2, 6] and facts["SIGMA_CAPS"] == [2, 3, 5, 5]


@pytest.mark.parametrize(
    "pid", ["66655555555421100000", "66555555555441000000", "66555555555431100001", "", "6" * 20]
)
def test_wrong_exact_profile_rejected(pid: str) -> None:
    with pytest.raises(ValueError, match="exact profile"):
        cert.theorem(pid)


@pytest.mark.parametrize(
    "change,message",
    [
        ({"wedges": 828}, "wedge"),
        ({"goodman": 294}, "Goodman"),
        ({"core": 14, "zeros": 6}, "K/Z"),
        ({"split_constant": 237}, "split constant"),
        ({"split_constant": 234}, "split constant"),
        ({"zeta_floor": 1}, "zeta floor"),
        ({"wedges": 825.0}, "noninteger"),
    ],
)
def test_wrong_wedge_goodman_kz_split_or_type_rejected(
    change: dict[str, int], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        cert.theorem(claim=replace(cert.CLAIM, **change))


@pytest.mark.parametrize(
    "change",
    [
        {"tickets": 19},
        {"triples": 21},
        {"pair_linearity": False},
        {"support_sizes": (2, 3, 4)},
        {"triples": 22.0},
    ],
)
def test_wrong_support_assumptions_rejected(change: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="support assumptions"):
        cert.theorem(assumptions=replace(cert.MODEL, **change))


def test_goodman_three_set_indicator_identity() -> None:
    pairs = ((0, 1), (0, 2), (1, 2))
    for bits in product((False, True), repeat=3):
        edges = {p for p, on in zip(pairs, bits, strict=True) if on}
        degrees = [sum(v in edge for edge in edges) for v in range(3)]
        homogeneous = int(len(edges) in (0, 3))
        assert homogeneous == 1 - Fraction(sum(g * (2 - g) for g in degrees), 2)


def test_split_identity_and_each_nonnegative_remainder_part() -> None:
    # An eight-vertex algebra fixture, not a target realization or a cap witness.
    k, z = set(range(5)), set(range(5, 8))
    graph = {(0, 5), (1, 5), (2, 6), (2, 7)}
    complement = set(combinations(range(8), 2)) - graph
    nbr = [{v if u == x else u for u, v in graph if x in (u, v)} for x in range(8)]
    m = {p for p in complement if set(p) <= k}
    n = {p for p in complement if set(p) <= z}

    def triangles(vertices: set[int]) -> int:
        return sum(set(combinations(t, 2)) <= complement for t in combinations(sorted(vertices), 3))

    parts = (
        triangles(k),
        triangles(z),
        sum(len(nbr[x] & nbr[y] & z) for x, y in m),
        sum(len(nbr[u] & nbr[v] & k) for u, v in n),
    )
    assert parts == (10, 1, 1, 1) and all(p >= 0 for p in parts)
    head = len(z) * len(m) + len(k) * len(n)
    head -= sum(len(nbr[x] & z) * sum(x in e for e in m) for x in k)
    head -= sum(len(nbr[x] & k) * sum(x in e for e in n) for x in z)
    actual = triangles(k | z)
    assert actual == head + sum(parts) == 34
    for part in parts:
        assert head + sum(parts) - part != actual  # Removing any part breaks exactness.


def test_independent_exhaustive_relaxation_and_every_argmax() -> None:
    # Different enumeration and an expanded polynomial; no cert upper helper is used.
    counts: Counter[tuple[int, ...]] = Counter()
    for included in product((False, True), repeat=10):
        edges = [p for p, on in zip(combinations(range(5), 2), included, strict=True) if on]
        zeta = tuple(sorted(6 - sum(v in e for e in edges) for v in range(5)))
        counts[zeta] += 1
    assert len(counts) == 31 and sum(counts.values()) == 1024
    assert dict((z, len(masks)) for z, masks in cert.zero_shapes()) == counts
    assert sorted(mask for _, masks in cert.zero_shapes() for mask in masks) == list(range(1024))
    best, states, labelled = -1, 0, 0
    peaks: set[tuple[tuple[int, ...], int, tuple[int, ...]]] = set()
    for a, b, c, d, h in product(range(3), range(4), range(6), range(6), range(10)):
        for zeta, multiplicity in counts.items():
            if a + b + c + d + h != sum(zeta):
                continue
            states += 1
            labelled += multiplicity
            u = 231 + a * a - 6 * a + b * b - 5 * b + c * c - 3 * c + d * d - 3 * d - 6 * h
            u += sum(z * z - 2 * z for z in zeta)
            if u > best:
                best = u
                peaks.clear()
            if u == best:
                peaks.add(((a, b, c, d), h, zeta))
    relaxation = cert.relaxation()
    observed = {
        (
            tuple(cast(list[int], s["SIGMA_LOW"])),
            cert.integer(s["H5_ACTIVE"]),
            tuple(cast(list[int], s["ZETA"])),
        )
        for s in cast(list[dict[str, object]], relaxation["ALL_ARGMAX_STATES"])
    }
    assert best == relaxation["CAP"] == 255
    assert states == relaxation["RELAXATION_STATES"] == 3788
    assert labelled == relaxation["LABELLED_RELAXATION_STATES"] == 106360
    assert peaks == observed and len(peaks) == 6
    assert all(sigma == (2, 3, 5, 5) for sigma, _, _ in peaks)
    assert relaxation["SIGMA_H_VECTORS"] == 4320 and relaxation["PRUNING"] == "NONE"


@pytest.mark.parametrize(
    "sigma,h,zeta,message",
    [
        ([3, 3, 5, 5], 0, [2, 2, 4, 4, 4], "ranges"),
        ([2, 3, 5, 5], 10, [3, 5, 5, 6, 6], "ranges"),
        ([2, 3, 5, 5], 1, [2, 2, 4, 4, 5], "degree sum"),
        ([2, 3, 5, 5], 1, [1, 3, 4, 4, 4], "ranges"),
        ([2, 3, 5, 5], 1.0, [2, 2, 4, 4, 4], "ranges"),
    ],
)
def test_wrong_relaxation_states_rejected(
    sigma: list[int], h: int, zeta: list[int], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        cert.state_upper(sigma, h, zeta)


def test_all_old_new_envelope_terms_endpoints_and_argmax(result: dict[str, object]) -> None:
    assert (result["OLD_T_CAP"], result["NEW_PROVEN_T_CAP"]) == (266, 255)
    assert result["OLD_ROW_BOUND"] == 313394776 and result["NEW_ROW_BOUND"] == 313296388
    assert result["ROW_DELTA"] == 98388
    degrees = [6 + int(v) for v in cert.TARGET]
    c3 = sum(comb(g, 3) for g in degrees)
    for label, cap in (("OLD", 266), ("NEW", 255)):
        terms = cast(list[cert.Term], result[f"{label}_ALL_T_TERMS"])
        assert len(terms) == result[f"{label}_TERM_COUNT"] == cap - 21
        assert [row[0] for row in terms] == list(range(22, cap + 1))
        for t, bound, k4, contained, s4, s3 in terms:
            opened = 825 - 3 * t
            assert k4 == max(0, -(-(c3 - 10 * opened) // 4))
            assert contained == min(k4, 196)
            assert s4 == max(112, 448 * contained + 679 * (k4 - contained))
            assert s3 == 2800 * opened + 20272 * (t - 22) + 154000
            exact = Fraction(308390040 + s3) - Fraction(4 * s4, 7)
            assert bound == -(-exact.numerator // exact.denominator)
        peak = max(row[1] for row in terms)
        assert result[f"{label}_ALL_ARGMAX"] == [row for row in terms if row[1] == peak]
        assert terms[0] == (22, 310669176, 0, 0, 112, 2279200)
    assert result["OLD_ALL_ARGMAX"] == [(266, 313394776, 508, 196, 299656, 5175968)]
    assert result["NEW_ALL_ARGMAX"] == [(255, 313296388, 425, 196, 243299, 5045376)]
    assert cert.obj(result["S4_AUTHORITY"])["INHERITED_FLOOR"] == 112
    assert cert.obj(result["S5_AUTHORITY"])["USED"] is False
    assert cert.obj(result["S5_AUTHORITY"])["VALUE"] is None


@pytest.mark.parametrize("label,cap", [("OLD", 266), ("NEW", 255)])
def test_every_missing_envelope_term_rejected(
    result: dict[str, object], label: str, cap: int
) -> None:
    terms = cast(list[cert.Term], result[f"{label}_ALL_T_TERMS"])
    for omitted in range(len(terms)):
        with pytest.raises(ValueError, match="incomplete T envelope"):
            cert.validate_envelope(cert.TARGET, cap, 112, terms[:omitted] + terms[omitted + 1 :])


@pytest.mark.parametrize("cap", [254, 256, True, 276])
def test_wrong_cap_rejected(result: dict[str, object], cap: int) -> None:
    with pytest.raises(ValueError, match=r"profile/cap|incomplete T envelope"):
        cert.validate_envelope(
            cert.TARGET, cap, 112, cast(list[cert.Term], result["NEW_ALL_T_TERMS"])
        )


def test_final_floor_wrong_k4_and_s4_direction_rejected() -> None:
    terms = cert.envelope(255, 113)  # Fractional probe; the certified inherited floor remains 112.
    row = terms[0]
    exact = Fraction(308390040 + row[5]) - Fraction(4 * row[4], 7)
    assert exact.denominator == 7
    changed = list(terms)
    changed[0] = (row[0], exact.numerator // exact.denominator, *row[2:])
    with pytest.raises(ValueError, match="ceiling rounding"):
        cert.validate_envelope(cert.TARGET, 255, 113, changed)
    changed = list(terms)
    last = terms[-1]
    changed[-1] = (last[0], last[1], last[2] - 1, *last[3:])
    with pytest.raises(ValueError, match="K4 rounding"):
        cert.validate_envelope(cert.TARGET, 255, 113, changed)
    changed[-1] = (*last[:4], last[4] + 112, last[5])
    with pytest.raises(ValueError, match="S4 direction"):
        cert.validate_envelope(cert.TARGET, 255, 113, changed)


@pytest.mark.parametrize("path", [cert.r1.SOURCE, cert.INPUT_RESULT])
def test_damaged_source_or_result_pin_rejected(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    original = cert.r2.git

    def damaged(*args: str) -> bytes:
        raw = original(*args)
        return raw + b"\n" if args[0] == "show" and args[1].endswith(path) else raw

    monkeypatch.setattr(cert.r2, "git", damaged)
    with pytest.raises(ValueError, match="blob pin"):
        cert.fixed_input()


def test_wrong_tree_digest_duplicate_json_and_rows_rejected(result: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="tree pin"):
        cert.identity(cert.INPUT_HEAD, cert.R2_TREE)
    with pytest.raises(ValueError, match="blob pin"):
        cert.blob(cert.INPUT_HEAD, cert.INPUT_RESULT, "0" * 64)
    with pytest.raises(ValueError, match="duplicate JSON"):
        cert.decode(b'{"row":1,"row":2}')
    rows = cast(dict[str, int], result["RESOLVED_ROW_BOUNDS_AFTER"])
    for damaged in (list(rows.items())[:-1], list(rows.items()) + list(rows.items())[:1]):
        with pytest.raises(ValueError, match="resolved rows"):
            cert.r2.checked_rows(damaged, rows)


@pytest.mark.parametrize(
    "field,value",
    [("NEW_PROVEN_T_CAP", 254), ("SOURCE_SHA256", "0" * 64), ("FAMILY_AFTER", 313296388)],
)
def test_tampered_result_rejected(result: dict[str, object], field: str, value: object) -> None:
    changed = deepcopy(result)
    changed[field] = value
    with pytest.raises(ValueError, match="not exactly reproducible"):
        replay_certificate_call(cert.__name__, "verify_result", changed)


def test_all_family_rows_cursor_floor_and_all_owners(result: dict[str, object]) -> None:
    before = cast(dict[str, int], result["RESOLVED_ROW_BOUNDS_BEFORE"])
    after = cast(dict[str, int], result["RESOLVED_ROW_BOUNDS_AFTER"])
    cursor = cert.obj(result["CURSOR"])
    coarse = cast(dict[str, int], cursor["COARSE_BOUND_PROJECTION"])
    assert len(before) == len(after) == 4647 and len(coarse) == 197
    assert set(before) == set(after) and not set(after) & set(coarse)
    assert [p for p in before if before[p] != after[p]] == [cert.TARGET]
    assert result["OTHER_RESOLVED_ROWS_UNCHANGED"] == 4646
    fixed = cert.decode(
        cert.blob(cert.INPUT_HEAD, cert.INPUT_RESULT, cert.INPUT_PINS[cert.INPUT_RESULT])
    )
    assert cursor == fixed["CURSOR"]
    assert (
        result["CURSOR_SHA256_BEFORE"]
        == result["CURSOR_SHA256_AFTER"]
        == cert.sha(cert.render(cursor))
    )
    merged = after | coarse
    levels = sorted(set(merged.values()), reverse=True)
    owners = sorted(p for p, bound in merged.items() if bound == levels[0])
    assert levels[:2] == [313394584, 313392516]
    assert result["ALL_NEW_MAX_OWNERS"] == owners and len(owners) == 41
    assert set(owners) <= set(coarse)
    assert result["FAMILY_BEFORE"] == 313394776 and result["FAMILY_AFTER"] == 313394584
    assert result["FAMILY_DELTA"] == 192 != result["ROW_DELTA"]
    assert result["CURSOR_IS_HIGHEST_BOTTLENECK"] is True
    assert result["NEXT_DISTINCT_BOUND"] == 313392516
    assert result["FRONTIER_FLOOR"] == result["CURSOR_MAXIMUM"] == 313394584
    assert result["INCUMBENT"] == 313263888
    assert result["OLD_GAP_TO_INCUMBENT"] == 130888
    assert result["GAP_TO_INCUMBENT"] == result["FRONTIER_FLOOR_GAP"] == 130696


def test_stored_result_full_reproduction_and_no_authority_inflation(
    result: dict[str, object],
) -> None:
    assert cert.RESULT.read_bytes() == cert.render(result)
    assert result["TASK_STATUS"] == "PROVEN_IMPROVEMENT"
    assert result["GLOBAL_OPTIMUM"] == "UNKNOWN" and result["PREDICTION_GAIN_CLAIMED"] is False
    assert result["CANONICAL_AUTHORITY_CHANGED"] == result["REMOTE_WRITE"] == "NO"
    assert result["PRODUCTION_MUTATION"] == "NONE"
    assert (
        result["SOLVER_CALLS"]
        == result["FULL_SUPPORT_GRAPHS_ENUMERATED"]
        == result["PORTFOLIOS_ENUMERATED"]
        == 0
    )
    assert str(result["GRAPH_ENUMERATION_COMPLETENESS"]).startswith("NOT_RUN")
    assert len(cert.obj(result["SOURCE_PINS"])) == 22
