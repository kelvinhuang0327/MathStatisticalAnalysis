"""Independent integer checks of the single-owner universal inequality."""

from __future__ import annotations

import copy
import json
from itertools import combinations, pairwise
from math import comb
from typing import Any
from unittest.mock import patch

import pytest

from lottolab.research import b649_min_s2_current_family_owner_exact_bound_r1 as x


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return x.compute_result()


def test_owner_minimum_degree_proof_all_possible_supports() -> None:
    d = tuple(int(c) for c in x.OWNER)
    assert len(d) == 20 and sum(d) == 66 and d.count(6) == 2
    assert d.count(4) == 1 and d.count(5) == 10
    low_vertex = d.index(4)
    candidates = list(combinations([i for i, value in enumerate(d) if value], 3))
    assert len(candidates) == 286
    assert sum(low_vertex in s for s in candidates) == 66
    for support in candidates:
        limit = 8 if low_vertex in support else 9
        assert min(6 + d[v] - 2 for v in support) <= limit
    # In any realization the unique low vertex occurs exactly d_v=4 times.
    assert 4 * 8 + (22 - 4) * 9 == x.contained_cap() == 194
    assert sum(value * (value + 4) for value in d) == 602
    assert 602 // 3 == 200


@pytest.mark.parametrize("profile", [tuple([0] * 20), tuple(map(int, "66655555555440000000"))])
def test_lemma_does_not_generalize_to_another_owner(profile: tuple[int, ...]) -> None:
    with pytest.raises(AssertionError, match="outside designated owner"):
        x.contained_cap(profile)


@pytest.mark.parametrize("cap", [193, 195, True, 200.0])
def test_unproved_or_noninteger_cap_rejected(cap: int) -> None:
    with pytest.raises(AssertionError, match="unproved A cap"):
        x.envelope(cap)


def test_all_243_terms_independent_integer_division_and_rounding(result: dict[str, Any]) -> None:
    # Independent divisions use quotient/remainder, not the module's ceiling expression.
    degrees = [12, 12, *[11] * 10, 10, *[6] * 7]
    w = sum(g * (g - 1) // 2 for g in degrees)
    j = sum(g * (g - 1) * (g - 2) // 6 for g in degrees)
    assert (w, j) == (832, 2350)
    for key, a_cap, maximum in (
        ("OLD_ALL_T_TERMS", 200, 313398920),
        ("NEW_ALL_T_TERMS", 194, 313398128),
    ):
        terms = result[key]
        assert [row[0] for row in terms] == list(range(22, 265))
        for t, bound, k4, contained, s4, s3, credit in terms:
            excess = j - 10 * (w - 3 * t)
            q, remainder = divmod(excess, 4)
            assert k4 == max(0, q + int(remainder != 0))
            assert contained == min(k4, a_cap)
            assert s4 == max(112, 679 * k4 - 231 * contained)
            expected_credit, residual = divmod(4 * s4, 7)
            assert credit == expected_credit and 0 <= residual <= 6
            assert s3 == 2800 * w + 11872 * t - 291_984
            assert bound == 308_390_040 + s3 - credit
            # The reported integer bound is >= the exact rational upper bound.
            assert 0 <= 7 * bound - (7 * (308_390_040 + s3) - 4 * s4) < 7
        assert max(row[1] for row in terms) == maximum == terms[-1][1]
        assert all(a[1] < b[1] for a, b in pairwise(terms))
    assert result["NEW_ALL_T_TERMS"][-1] == [264, 313398128, 488, 194, 286538, 5171824, 163736]
    assert result["NEW_ALL_T_TERMS"][-2][1] == 313389360


def test_neighbourhood_missing_pair_inequality_on_all_four_vertex_graphs() -> None:
    pairs = list(combinations(range(4), 2))
    for mask in range(1 << len(pairs)):
        edges = {pair for i, pair in enumerate(pairs) if mask & (1 << i)}
        missing = len(pairs) - len(edges)
        triangles = sum(
            all(edge in edges for edge in combinations(s, 2)) for s in combinations(range(4), 3)
        )
        assert triangles >= comb(4, 3) - (4 - 2) * missing


def independent_k4_weight(has_triple: bool) -> int:
    # Distinct-support label choices, without capped-hit DP states.
    supports = (7, 9, 10, 12) if has_triple else (3, 5, 9, 6, 10, 12)
    singleton_counts = [6 - sum(bool(mask & (1 << i)) for mask in supports) for i in range(4)]
    outside = 49 - len(supports) - sum(singleton_counts)
    total = 0
    for selected in range(1 << len(supports)):
        chosen = [mask for i, mask in enumerate(supports) if selected & (1 << i)]
        needs = [max(0, 3 - sum(bool(mask & (1 << i)) for mask in chosen)) for i in range(4)]

        def fill(vertex: int, used: int, ways: int, needs: list[int] = needs) -> int:
            if vertex == 4:
                return ways * comb(outside, 7 - used) if 0 <= 7 - used <= outside else 0
            return sum(
                fill(vertex + 1, used + take, ways * comb(singleton_counts[vertex], take))
                for take in range(needs[vertex], min(singleton_counts[vertex], 7 - used) + 1)
            )

        total += fill(0, len(chosen), 1)
    return 7 * total


@pytest.mark.parametrize(("triple", "weight"), [(True, 448), (False, 679)])
def test_k4_weights_with_independent_support_subset_enumeration(triple: bool, weight: int) -> None:
    assert independent_k4_weight(triple) == x.k4_weight(triple) == weight


def test_inequality_and_substitution_directions() -> None:
    for r in range(8):
        assert 7 * (r - comb(r, 2) + comb(r, 3) - int(r > 0)) >= 4 * comb(r, 4)
    assert comb(7, 2) // comb(3, 2) == 7
    assert 8 * comb(3, 2) > comb(7, 2)
    # Lower K and upper A give a lower S4 contribution for every allowed A.
    for k4 in (0, 193, 194, 195, 488, 489):
        floor = 679 * k4 - 231 * min(k4, 194)
        for actual_k4 in (k4, k4 + 1):
            assert all(
                448 * a + 679 * (actual_k4 - a) >= floor for a in range(min(actual_k4, 194) + 1)
            )


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("PROFILE_IDS", ["66655555555440000000"]),
        ("STATUS", "UNKNOWN"),
        ("STATUS", "FEASIBLE"),
        ("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND", 263),
        ("REFUTED_GRAPH_TRIANGLE_COUNT", 264),
        ("EXTERNAL_TIMEOUT_EXIT_CODE", 124),
    ],
)
def test_inherited_cap_scope_and_disposition_tampering_rejected(key: str, value: object) -> None:
    authority, cap = x.authorities()
    with pytest.raises(AssertionError, match="cap certificate mismatch"):
        x.validate_authority(authority, {**cap, key: value})


def test_frozen_input_digest_tampering_rejected() -> None:
    with (
        patch.dict(x.INPUT_SHA256, {x.AUTHORITY_PATH: "0" * 64}),
        pytest.raises(AssertionError, match="frozen input changed"),
    ):
        x.authorities()


def test_baseline_and_family_effect_no_winner_claim(result: dict[str, Any]) -> None:
    assert result["BOUND_DELTA"] == 792
    effect = result["FAMILY_BOUND_EFFECT"]
    assert effect["AFTER"] == max(313398128, 313398532) == 313398532
    assert effect["DELTA"] == 388 and effect["OWNER_BELOW_NEXT_BY"] == 404
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["STRICT_WINNER_DISCOVERED"] == "NO"
    assert result["SOLVER_CALLS"] == 0 and result["UNPROVED_ASSUMPTIONS"] == []
    assert result["CERTIFICATE_F_MUTATED_OR_RECOMPUTED"] == "NO"


def test_new_bound_guard_is_falsifiable() -> None:
    # Controlled mutation seam; changing the asserted bound must fail verification.
    with (
        patch.object(x, "NEW_BOUND", x.OLD_BOUND),
        pytest.raises(AssertionError, match="new envelope mismatch"),
    ):
        x.compute_result()
    assert x.compute_result()["NEW_ADMISSIBLE_OWNER_BOUND"] == 313398128


def test_family_baseline_tampering_rejected() -> None:
    authority, cap = x.authorities()
    altered = copy.deepcopy(authority)
    altered["RESOLVED_ROW_BOUNDS"][x.OWNER] -= 1
    with pytest.raises(AssertionError, match="owner baseline mismatch"):
        x.validate_authority(altered, cap)


def test_saved_exact_result(result: dict[str, Any]) -> None:
    saved = json.loads(x.RESULT_PATH.read_text())
    execution = saved.pop("EXECUTION")
    assert execution["CPU_LIMIT_SECONDS"] == 120 and execution["CPU_BOUND_PROCESSES"] == 1
    assert saved == result
