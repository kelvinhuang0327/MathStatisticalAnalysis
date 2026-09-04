"""Clean-room independent tests for the GKP covering-number upper-bound core.

No fixtures here are drawn from any donor implementation or dataset. Toy
examples are verified by hand against the published GKP Section V recurrence
and, where possible, cross-checked against the independent Schoenheim (1964)
lower bound so that an exact value is self-certifying (lower bound == upper
bound implies both are the true covering number).
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import inspect
import math

import pytest

from lottolab.research import covering_design_gkp_bound as gkp
from lottolab.research.covering_design_gkp_bound import (
    CoveringBoundClassification,
    covering_number_upper_bound,
    schoenheim_lower_bound,
)

# ---------------------------------------------------------------------------
# 1. Invalid parameters
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "v, k, t",
    [
        (3, 5, 2),  # v < k
        (5, 2, 3),  # k < t
        (5, 3, -1),  # t < 0
        (-1, 3, 1),  # v < 0 (and v < k)
    ],
)
def test_invalid_parameter_ordering_raises(v: int, k: int, t: int) -> None:
    with pytest.raises(ValueError):
        covering_number_upper_bound(v, k, t)


@pytest.mark.parametrize("bad", [2.0, "3", None, True, False])
def test_invalid_parameter_type_raises(bad: object) -> None:
    with pytest.raises(ValueError):
        covering_number_upper_bound(bad, 3, 2)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 2. Trivial cases
# ---------------------------------------------------------------------------


def test_trivial_t_zero() -> None:
    result = covering_number_upper_bound(7, 4, 0)
    assert result.upper_bound == 1
    assert result.classification == CoveringBoundClassification.TRIVIAL_EXACT
    assert result.rule == "TRIVIAL_T_ZERO"


def test_trivial_k_equals_v() -> None:
    result = covering_number_upper_bound(6, 6, 3)
    assert result.upper_bound == 1
    assert result.classification == CoveringBoundClassification.TRIVIAL_EXACT
    assert result.rule == "TRIVIAL_K_EQUALS_V"


@pytest.mark.parametrize(
    "v, k, expected",
    [(10, 3, 4), (9, 3, 3), (7, 2, 4)],
)
def test_trivial_t_one_is_ceil_v_over_k(v: int, k: int, expected: int) -> None:
    result = covering_number_upper_bound(v, k, 1)
    assert result.upper_bound == expected == math.ceil(v / k)
    assert result.classification == CoveringBoundClassification.TRIVIAL_EXACT
    assert result.rule == "TRIVIAL_T_EQUALS_ONE"


def test_trivial_t_one_value_correct_when_k_equals_v_too() -> None:
    # v == k == t == 1 satisfies both the k==v and t==1 trivial rules; the
    # k==v rule is checked first, but the value (1) is identical either way.
    result = covering_number_upper_bound(1, 1, 1)
    assert result.upper_bound == 1 == math.ceil(1 / 1)
    assert result.classification == CoveringBoundClassification.TRIVIAL_EXACT


def test_trivial_t_equals_k_is_binomial() -> None:
    result = covering_number_upper_bound(8, 3, 3)
    assert result.upper_bound == math.comb(8, 3)
    assert result.classification == CoveringBoundClassification.TRIVIAL_EXACT
    assert result.rule == "TRIVIAL_T_EQUALS_K"


# ---------------------------------------------------------------------------
# 3. Published recurrence on a hand-checkable toy example
# ---------------------------------------------------------------------------


def test_gkp_recurrence_matches_hand_derivation_for_c_4_3_2() -> None:
    """C(4,3,2): 4 points, cover every pair with 3-point blocks.

    By hand: the 4 distinct 3-subsets of a 4-set already give the trivial
    bound comb(4,3)=4, but 3 of them already cover all 6 pairs (e.g. drop
    the block that omits point 1: blocks {1,2,3},{1,2,4},{1,3,4} jointly
    cover {1,2},{1,3},{2,3},{1,4},{2,4},{3,4} — every pair). So the true
    value is 3, strictly better than the trivial complete enumeration.
    """

    result = covering_number_upper_bound(4, 3, 2)
    assert result.upper_bound == 3
    assert result.classification == CoveringBoundClassification.CONSTRUCTIVE_UPPER_BOUND
    assert result.rule == "GKP_SECTION5_INTERVAL_DP"
    assert result.provenance == ("split_v1=2", "split_v2=2")


# ---------------------------------------------------------------------------
# 4. Section-5 direct-combination arithmetic
# ---------------------------------------------------------------------------


def test_direct_combination_candidate_arithmetic_v1_2_v2_2_k_3_t_2() -> None:
    # C(2,1,0)=1 (trivial t=0); C(2,2,2)=1 (trivial k=v); C(2,1,1)=2
    # (trivial t=1, ceil(2/1)); C(2,2,1)=1 (trivial k=v); C(2,2,0)=1.
    direct = gkp._direct_combination_candidate

    # i=j=0: ell in [max(0, 3-2), min(3-2+0, 2, 3)] = [1,1].
    # C(2,1,0) * C(2,2,2) = 1 * 1 = 1.
    assert direct(2, 2, 3, 2, 0, 0) == 1

    # i=j=1: ell in [max(1,1), min(3-2+1,2,3)] = [1,2].
    # ell=1: C(2,1,1)*C(2,2,1) = 2*1 = 2. ell=2: C(2,2,1)*C(2,1,1) = 1*2 = 2.
    assert direct(2, 2, 3, 2, 1, 1) == 2

    # i=j=2: ell in [max(2,1), min(3-2+2,2,3)] = [2,2].
    # C(2,2,2) * C(2,1,0) = 1 * 1 = 1.
    assert direct(2, 2, 3, 2, 2, 2) == 1

    # i=0, j=2 (the full range): ell in [max(2,1), min(3-2+0,2,3)] = [2,1],
    # an empty range, so the direct candidate is infeasible.
    assert direct(2, 2, 3, 2, 0, 2) is None


# ---------------------------------------------------------------------------
# 5. Interval split arithmetic
# ---------------------------------------------------------------------------


def test_interval_split_beats_infeasible_direct_candidate() -> None:
    # c[0][2] has no direct candidate (see test above), so it must be
    # resolved purely by splitting: c[0][2] = min(c[0][r] + c[r+1][2])
    # for r in {0, 1} = min(c[0][0]+c[1][2], c[0][1]+c[2][2]).
    # c[0][0] = 1, c[2][2] = 1 (direct, as derived above).
    # c[0][1] = min(direct(0,1)=2, c[0][0]+c[1][1]=1+2=3) = 2.
    # c[1][2] = min(direct(1,2)=2, c[1][1]+c[2][2]=2+1=3) = 2.
    # So c[0][2] = min(1+2, 2+1) = 3, and no direct candidate beats it.
    bound = gkp._gkp_section5_upper_bound(2, 2, 3, 2)
    assert bound == 3


# ---------------------------------------------------------------------------
# 6. Monotonic sanity properties implied by the implemented rules
# ---------------------------------------------------------------------------


def _bound_value(v: int, k: int, t: int) -> int:
    result = covering_number_upper_bound(v, k, t).upper_bound
    assert result is not None
    return result


def test_t_one_bound_is_monotonic_nondecreasing_in_v() -> None:
    k = 4
    values = [_bound_value(v, k, 1) for v in range(4, 20)]
    assert values == sorted(values)


def test_t_one_bound_is_monotonic_nonincreasing_in_k() -> None:
    v = 20
    values = [_bound_value(v, k, 1) for k in range(1, v + 1)]
    assert values == sorted(values, reverse=True)


def test_t_equals_k_bound_is_monotonic_nondecreasing_in_v() -> None:
    k = 3
    values = [_bound_value(v, k, k) for v in range(3, 12)]
    assert values == sorted(values)


@pytest.mark.parametrize(
    "v, k, t",
    [(4, 3, 2), (5, 3, 2), (6, 4, 2), (6, 4, 3), (7, 4, 2), (7, 5, 3)],
)
def test_upper_bound_never_below_schoenheim_lower_bound(v: int, k: int, t: int) -> None:
    upper = covering_number_upper_bound(v, k, t).upper_bound
    lower = schoenheim_lower_bound(v, k, t)
    assert upper is not None
    assert upper >= lower


def test_exact_value_c_5_3_2_certified_by_matching_lower_bound() -> None:
    # When the constructed upper bound equals the independent Schoenheim
    # lower bound, both are provably the true covering number - a
    # self-certifying exactness check requiring no external data.
    upper = covering_number_upper_bound(5, 3, 2).upper_bound
    lower = schoenheim_lower_bound(5, 3, 2)
    assert upper == lower == 4


# ---------------------------------------------------------------------------
# 7. Deterministic repeat
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("v, k, t", [(4, 3, 2), (7, 4, 2), (9, 5, 3), (10, 6, 1)])
def test_deterministic_repeat(v: int, k: int, t: int) -> None:
    first = covering_number_upper_bound(v, k, t)
    second = covering_number_upper_bound(v, k, t)
    assert first == second

    gkp.clear_cache()
    third = covering_number_upper_bound(v, k, t)
    assert first == third


# ---------------------------------------------------------------------------
# 8. Never exceeds the trivial complete-enumeration bound C(v, k)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "v, k, t",
    [(4, 3, 2), (5, 3, 2), (6, 4, 2), (6, 4, 3), (7, 4, 2), (8, 5, 3), (9, 6, 4)],
)
def test_upper_bound_never_exceeds_complete_enumeration(v: int, k: int, t: int) -> None:
    result = covering_number_upper_bound(v, k, t)
    assert result.upper_bound is not None
    assert result.upper_bound <= math.comb(v, k)


# ---------------------------------------------------------------------------
# 9. No external data or network dependency
# ---------------------------------------------------------------------------


def test_module_has_no_network_or_persistence_imports() -> None:
    source = inspect.getsource(gkp)
    forbidden_substrings = [
        "requests",
        "urllib",
        "httpx",
        "socket",
        "sqlite3",
        "http.client",
    ]
    for token in forbidden_substrings:
        assert token not in source


# ---------------------------------------------------------------------------
# 10. No donor-code identifiers or donor-specific structures
# ---------------------------------------------------------------------------


def test_module_has_no_donor_identifiers() -> None:
    # LJCR/Zenodo are intentionally named in the module docstring's own
    # data-dependence disclaimer ("no LJCR/Zenodo dataset dependence") and
    # are not donor-code identifiers; they are excluded from this scan.
    source = inspect.getsource(gkp)
    forbidden_identifiers = [
        "architrahul",
        "Pareto-polymer-enumerator",
        "DelieverThibaut",
        "CoveringDesignProblem",
        "TabuSearch",
        "weaken",
        "lift",
    ]
    for token in forbidden_identifiers:
        assert token not in source
