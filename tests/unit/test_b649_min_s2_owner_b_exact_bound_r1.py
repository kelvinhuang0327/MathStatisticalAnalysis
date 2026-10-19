"""Independent degree coverage, exact arithmetic and adversarial Owner B checks."""

from __future__ import annotations

import copy
from fractions import Fraction
from itertools import combinations_with_replacement, product
from math import comb

import pytest

from lottolab.research import b649_min_s2_owner_b_exact_bound_r1 as c


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return c.compute_result()


def havel_hakimi(degrees: tuple[int, ...]) -> bool:
    if any(d < 0 or d >= len(degrees) for d in degrees):
        return False
    remaining = list(degrees)
    while remaining:
        remaining.sort(reverse=True)
        degree = remaining.pop(0)
        if degree == 0:
            return True
        if degree > len(remaining):
            return False
        for i in range(degree):
            remaining[i] -= 1
        if any(d < 0 for d in remaining):
            return False
    return True


def bipartite_havel_hakimi(left: tuple[int, ...], right: tuple[int, ...]) -> bool:
    if sum(left) != sum(right):
        return False
    remaining = list(right)
    for degree in sorted(left, reverse=True):
        remaining.sort(reverse=True)
        if degree > len(remaining):
            return False
        for i in range(degree):
            remaining[i] -= 1
        if any(d < 0 for d in remaining):
            return False
    return not any(remaining)


def test_complete_necessary_coverage_with_independent_algorithms(result: dict[str, object]) -> None:
    d = (6,) * 4 + (5,) * 6 + (4,) * 2 + (3, 1)
    zero_by_sum: dict[int, list[tuple[int, ...]]] = {}
    for zeta in combinations_with_replacement(range(1, 7), 6):
        zero_by_sum.setdefault(sum(zeta), []).append(zeta)
    rows: list[list[object]] = []
    balanced = 0
    for d5, d4, d3, d1 in product(
        combinations_with_replacement((0, 1), 6),
        combinations_with_replacement((0, 1, 2), 2),
        range(4),
        range(6),
    ):
        sigma = (0,) * 4 + d5 + d4 + (d3, d1)
        for zeta in zero_by_sum.get(sum(sigma), []):
            balanced += 1
            h = tuple(7 - v + s for v, s in zip(d, sigma, strict=True))
            a = tuple(v - 1 for v in zeta)
            residual = tuple(6 - v - s for v, s in zip(d, sigma, strict=True))
            if not all(havel_hakimi(seq) for seq in (h, a, residual, tuple(6 - v for v in zeta))):
                continue
            if not bipartite_havel_hakimi(sigma, zeta):
                continue
            r = sum(sigma)
            f = 297 - 6 * ((32 + r) // 2) - 14 * ((r - 6) // 2)
            f += sum(s * degree for s, degree in zip(sigma, h, strict=True))
            f += sum(z * degree for z, degree in zip(zeta, a, strict=True))
            rows.append([list(sigma), list(zeta), list(h), list(a), f])
    proof = c.obj(result["THEOREM"])
    assert balanced == proof["BALANCED_RANGE_COUNT"] == 5113
    assert len(rows) == proof["NECESSARY_COUNT"] == 957
    assert rows == proof["ALL_NECESSARY_CONFIGURATIONS"]
    assert max(c.integer(r[-1]) for r in rows) == proof["T_CAP"] == 243
    assert proof["COMPLEMENT_TRIANGLE_FLOOR"] == 54
    assert c.sha(c.render(rows)) == proof["CONFIGURATIONS_SHA256"]


def test_independent_model_and_complete_envelopes(result: dict[str, object]) -> None:
    d = tuple(map(int, c.TARGET))
    g = [6 + v for v in d]
    assert sum(g) == 186 and sum(comb(v, 2) for v in g) == 831
    assert comb(20, 3) - sum(v * (19 - v) for v in g) // 2 == 297
    terms: list[list[int]] = []
    for t in range(22, 265):
        k4 = max(0, -(-(sum(comb(v, 3) for v in g) - 10 * (831 - 3 * t)) // 4))
        contained = min(k4, sum(v * (4 + v) for v in d) // 3)
        s4 = max(112, 679 * k4 - 231 * contained)
        s3 = 2800 * 831 + 11872 * (t - 22) - 30800
        exact = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
        bound = -(-exact.numerator // exact.denominator)
        assert bound - 1 < exact <= bound
        terms.append([t, bound, k4, contained, s4, s3])
    assert result["OLD_FULL_T_ENVELOPE"] == terms
    assert result["NEW_FULL_T_ENVELOPE"] == terms[:222]
    assert max(t[1] for t in terms) == result["CURRENT_PROFILE_BOUND"] == 313395344
    assert max(t[1] for t in terms[:222]) == result["NEW_FULL_PROFILE_BOUND"] == 313206948
    assert result["EXACT_PROFILE_DELTA"] == 188396
    assert result["STRICT_GAIN_EXCLUDED"] is True
    assert 313263888 - 313206948 == 56940
    assert result["CURRENT_S5_CAP"] is None and result["S5_USED"] is False
    thresholds = c.obj(result["MINIMUM_IMPROVEMENT"])
    assert thresholds["CAP_THRESHOLDS"] == {"313395343": 263, "313395164": 263}
    assert thresholds["PEAK_S4_THRESHOLDS"] == {"313395343": 286512, "313395164": 286825}


def test_graph_is_a_relaxation_and_complement_identity(result: dict[str, object]) -> None:
    graph = c.obj(result["GRAPH_COUNTEREXAMPLE_CHECK"])
    assert graph["T_G"] == 243 and graph["T_H"] == 54
    assert graph["P_TERMS"] == [0, 0, 0, 0]
    assert graph["SUPPORT_REALIZATION"] == "NOT_ASSERTED"
    assert c.obj(result["THEOREM"])["LEGAL_SUPPORT_ATTAINMENT"] == "UNKNOWN"


def test_exact_seal_full_family_and_status_preservation(result: dict[str, object]) -> None:
    path = c.result_path()
    assert path is not None and path.read_bytes() == c.render(result)
    assert path.name == f"{c.RESULT_PREFIX}{c.sha(path.read_bytes())}.json"
    sealed = c.decode(c.checked_source(c.BASE_RESULT, c.BASE_SHA))
    before = {p: c.integer(v) for p, v in c.obj(sealed["RESOLVED_ROW_BOUNDS"]).items()}
    after = {p: c.integer(v) for p, v in c.obj(result["RESOLVED_ROW_BOUNDS"]).items()}
    assert len(before) == len(after) == 4647 and set(before) == set(after)
    assert [p for p in before if before[p] != after[p]] == [c.TARGET]
    assert before[c.OTHER_OWNER] == after[c.OTHER_OWNER] == 313395344
    assert c.obj(result["CURSOR"]) == c.obj(sealed["CURSOR"])
    cursor = c.obj(result["CURSOR"])
    coarse = {p: c.integer(v) for p, v in c.obj(cursor["COARSE_BOUND_PROJECTION"]).items()}
    assert len(coarse) == 197 and max(coarse.values()) == 313394584
    assert not set(after).intersection(coarse)
    merged = {**after, **coarse}
    maximum = max(merged.values())
    assert maximum == result["FAMILY_AFTER_SINGLE_ROW"] == 313395344
    assert sorted(p for p, b in merged.items() if b == maximum) == [c.OTHER_OWNER]
    assert result["SINGLE_ROW_FAMILY_DELTA"] == 0
    assert result["BASE_PROVENANCE_VERBATIM"] == sealed["PROVENANCE"]
    assert (
        result["INHERITED_CAVEATS_AND_STATUS_VERBATIM"]
        == sealed["INHERITED_CAVEATS_AND_STATUS_VERBATIM"]
    )
    assert result["ORIGINAL_BONF5_STATUS"] == {
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "TASK_STATUS": "COMPLETE_SELF_CHECK_ONLY",
    }
    assert result["PRIOR_GENERIC_SPLIT_STATUS"] == "COMPLETE_SELF_CHECK_ONLY"
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"


@pytest.mark.parametrize(
    "sigma,zeta",
    [
        ((1,) + (0,) * 11 + (0, 5), (1,) * 6),
        ((0,) * 12 + (0, 6), (1,) * 6),
        ((0,) * 12 + (1, 5), (0, 1, 1, 1, 1, 2)),
        ((0,) * 12 + (1, 5), (1, 1, 1, 1, 1, 7)),
        ((0,) * 12 + (1, 5), (1, 1, 1, 1, 1, 2)),
    ],
)
def test_rejects_invalid_cross_capacities(sigma: tuple[int, ...], zeta: tuple[int, ...]) -> None:
    with pytest.raises(AssertionError):
        c.split_value(sigma, zeta)


@pytest.mark.parametrize("pid", [c.OTHER_OWNER, "66665555554430000000", c.TARGET[:-1]])
def test_rejects_wrong_profile(pid: str) -> None:
    with pytest.raises(AssertionError, match="exact profile"):
        c.theorem(pid)


def test_rejects_tampered_source_hash() -> None:
    with pytest.raises(AssertionError, match="tampered source hash"):
        c.checked_source(c.BASE_RESULT, "0" * 64)


@pytest.mark.parametrize("cap,bound", [(244, 313206948), (242, 313206948), (243, 313206947)])
def test_rejects_incorrect_cap_or_profile_bound(
    result: dict[str, object], cap: int, bound: int
) -> None:
    sealed = c.decode(c.checked_source(c.BASE_RESULT, c.BASE_SHA))
    with pytest.raises(AssertionError, match="incorrect cap or bound"):
        c.apply_one(sealed, c.TARGET, cap, bound)
    assert result["NEW_PROVEN_T_CAP"] == 243


@pytest.mark.parametrize("mutation", ["s4_sign", "floor", "s4_floor", "s3", "k4"])
def test_rejects_wrong_bound_terms(result: dict[str, object], mutation: str) -> None:
    row = [c.integer(v) for v in c.items(c.items(result["OLD_FULL_T_ENVELOPE"])[-1])]
    if mutation == "s4_sign":
        row[1] = (7 * (372228640 - 63838600 + row[5]) + 4 * row[4] + 6) // 7
    elif mutation == "floor":
        row[1] -= 1
    elif mutation == "s4_floor":
        row[4] += 1
    elif mutation == "s3":
        row[5] += 1
    else:
        row[2] += 1
    with pytest.raises(AssertionError, match="bound direction or rounding"):
        c.validate_term(c.exact_profile(c.TARGET), (row[0], row[1], row[2], row[3], row[4], row[5]))


def test_rejects_ledger_drift(result: dict[str, object]) -> None:
    sealed = c.decode(c.checked_source(c.BASE_RESULT, c.BASE_SHA))
    changed = copy.deepcopy(sealed)
    c.obj(changed["RESOLVED_ROW_BOUNDS"])[c.OTHER_OWNER] = 313395343
    with pytest.raises(AssertionError, match="ledger digest"):
        c.apply_one(changed, c.TARGET, 243, c.integer(result["NEW_FULL_PROFILE_BOUND"]))
