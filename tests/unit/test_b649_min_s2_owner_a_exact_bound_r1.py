"""Focused exact arithmetic, reduced-domain coverage and certificate tamper guards."""

from __future__ import annotations

import copy
from fractions import Fraction
from math import comb
from random import Random

import pytest

from lottolab.research import b649_min_s2_owner_a_exact_bound_r1 as c


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return c.compute_result()


def test_sealed_replay_and_scientific_result(result: dict[str, object]) -> None:
    assert c.RESULT.read_bytes() == c.render(result)
    proof = c.obj(result["CERTIFICATE"])
    assert proof["NEW_T_CAP"] == 249 and proof["H_TRIANGLE_FLOOR"] == 48
    assert proof["REDUCED_COUNT"] == 1405 and proof["EXPANDED_COUNT"] == 90879
    assert proof["ZERO_GRAPH_COUNT"] == 1024
    assert (
        proof["Q_TABLE_SHA256"]
        == "93f84881332f8ed4928a6a5509aa5b80931f87915c5f66ef3fe8001f4e55109e"
    )
    assert (
        proof["DOMAIN_SHA256"] == "db45591cc1565ae08a2eaeb661fc1abbcbefc7806df1982f6d78476b67ae1b3d"
    )
    assert proof["MAXIMIZERS"] == [[[0, 5, 5], 0, 10, 3, [2, 1, 1], 8, 257, 249]]
    assert result["NEW_FULL_PROFILE_BOUND"] == 313260720
    assert result["EXACT_PROFILE_DELTA"] == 134624
    assert result["GAP_TO_INCUMBENT"] == -3168 and result["STRICT_GAIN_EXCLUDED"] == "YES"


def test_independent_rational_envelope(result: dict[str, object]) -> None:
    d = list(map(int, c.TARGET))
    g = [6 + v for v in d]
    w = sum(comb(v, 2) for v in g)
    j = sum(comb(v, 3) for v in g)
    assert (w, j, sum(v * (v + 4) for v in d) // 3) == (831, 2350, 200)
    terms: list[list[int]] = []
    for t in range(22, 250):
        k4 = max(0, -(-(j - 10 * (w - 3 * t)) // 4))
        contained = min(200, k4)
        s4 = max(112, 448 * contained + 679 * (k4 - contained))
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        rational = Fraction(308390040 + s3) - Fraction(4 * s4, 7)
        bound = -(-rational.numerator // rational.denominator)
        assert bound - 1 < rational <= bound
        terms.append([t, bound, k4, contained, s4, s3])
    assert result["NEW_ROUTE_BOUND_TERMS"] == terms
    assert terms[-1] == [249, 313260720, 378, 200, 210462, 4990944]
    assert len(terms) == 228 and max(t[1] for t in terms) == 313260720
    assert c.official.r28.rows(result["CURRENT_ROUTE_BOUND_TERMS"])[:228] == terms


def test_ledger_cursor_and_inherited_statuses(result: dict[str, object]) -> None:
    sealed, _ = c.load_base()
    before = {p: c.integer(v) for p, v in c.obj(sealed["RESOLVED_ROW_BOUNDS"]).items()}
    cursor = c.obj(sealed["CURSOR"])
    after = c.project(list(before.items()), cursor, sealed, 313260720)
    assert len(after) == 4647
    assert {p for p in before if before[p] != after[p]} == {c.TARGET}
    assert after[c.OTHER] == 313395344
    coarse = c.obj(cursor["COARSE_BOUND_PROJECTION"])
    assert len(coarse) == 197 and max(map(c.integer, coarse.values())) == 313394584
    assert max([*after.values(), *map(c.integer, coarse.values())]) == 313395344
    assert result["SINGLE_ROW_FAMILY_DELTA"] == 0
    assert result["CURSOR_SHA256"] == sealed["CURSOR_SHA256"]
    assert c.obj(result["INHERITED_CAVEATS_REFERENCE"])["VALUE_SHA256"] == c.sha(
        c.render(sealed["INHERITED_CAVEATS_AND_STATUS_VERBATIM"])
    )
    assert result["ORIGINAL_BONF5_STATUS_VERBATIM"] == sealed["DONOR_ORIGINAL_STATUS_VERBATIM"]


def test_correction_direction_on_actual_small_neighbourhoods() -> None:
    # Samples only falsify local inequalities; universality follows from cardinality proof.
    rng = Random(649)
    for _ in range(120):
        s = [rng.randrange(6) for _ in range(3)]
        mask = rng.randrange(8)
        edges = [ij for k, ij in enumerate(c.LP) if mask & (1 << k)]
        ell = [sum(i in ij for ij in edges) for i in range(3)]
        core = [set(rng.sample(range(12), 7 + s[i] - ell[i])) for i in range(3)]
        zero = [set(rng.sample(range(5), v)) for v in s]
        actual = int(mask == 7) + sum(
            len(core[i] & core[j]) + len(zero[i] & zero[j]) for i, j in edges
        )
        assert c.correction(s, mask) <= actual


def test_all_labelled_low_vectors_have_sorted_domain_representatives() -> None:
    # The label permutation preserves feasibility and the entire correction.
    from itertools import permutations, product

    for s in product(range(6), repeat=3):
        perm = sorted(range(3), key=lambda i: s[i])
        sorted_s = tuple(s[i] for i in perm)
        for mask in range(8):
            edges = {ij for k, ij in enumerate(c.LP) if mask & (1 << k)}
            newmask = sum(
                1 << k
                for k, (i, j) in enumerate(c.LP)
                if tuple(sorted((perm[i], perm[j]))) in edges
            )
            assert c.low_allowed(s, mask) == c.low_allowed(sorted_s, newmask)
            assert c.correction(s, mask) == c.correction(sorted_s, newmask)
    assert len(list(permutations(range(3)))) == 6


@pytest.mark.parametrize("pid", [c.OTHER, "66655555555511000000", ""])
def test_wrong_profile_rejected(pid: str) -> None:
    with pytest.raises(AssertionError, match="profile"):
        c.certify(pid)


@pytest.mark.parametrize(
    "key,value", [("TICKETS", 19), ("TRIPLES", 21), ("PAIRS", 28), ("PAIR_LINEARITY", False)]
)
def test_invalid_assumptions_rejected(key: str, value: object) -> None:
    with pytest.raises(AssertionError, match="assumptions"):
        c.certify(model={**c.MODEL, key: value})


@pytest.mark.parametrize(
    "head,path,digest",
    [
        ("", c.BASE_RESULT, c.BASE_SHA),
        (c.BASE_HEAD, "", c.BASE_SHA),
        (c.BASE_HEAD, c.BASE_RESULT, ""),
        (c.BASE_HEAD, c.BASE_RESULT, "0" * 64),
    ],
)
def test_source_identity_tamper_rejected(head: str, path: str, digest: str) -> None:
    with pytest.raises(AssertionError):
        c.pinned(head, path, digest)


def test_bound_floor_mutation_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def bad(s3: int, s4: int) -> int:
        return (7 * (308390040 + s3) - 4 * s4) // 7

    monkeypatch.setattr(c, "rounded_bound", bad)
    with pytest.raises(AssertionError, match="rounding"):
        c.envelope(249)


@pytest.mark.parametrize("mutation", ["duplicate", "other_owner", "cursor", "bound"])
def test_family_tamper_rejected(mutation: str) -> None:
    sealed, _ = c.load_base()
    rows = [(p, c.integer(v)) for p, v in c.obj(sealed["RESOLVED_ROW_BOUNDS"]).items()]
    cursor = copy.deepcopy(c.obj(sealed["CURSOR"]))
    bound = 313260720
    if mutation == "duplicate":
        rows[-1] = rows[0]
    elif mutation == "other_owner":
        rows = [(p, v - int(p == c.OTHER)) for p, v in rows]
    elif mutation == "cursor":
        cursor["BOUND"] = 0
    else:
        bound -= 1
    with pytest.raises(AssertionError):
        c.project(rows, cursor, sealed, bound)
