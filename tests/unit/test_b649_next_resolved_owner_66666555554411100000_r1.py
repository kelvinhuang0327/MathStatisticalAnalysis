"""Focused falsifiable checks of the full-profile finite-superset certificate."""

from __future__ import annotations

import json
import resource
from itertools import combinations, combinations_with_replacement, product
from typing import cast
from unittest.mock import patch

import pytest

from lottolab.research import b649_next_resolved_owner_66666555554411100000_r1 as c


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("a search/proof entrypoint ran during read-only ledger replay")

    with (
        patch.object(c.frozen.split, "degree_configurations", forbidden),
        patch.object(c.frozen.split, "split_certificate", forbidden),
        patch.object(c.frozen.chase, "chase", forbidden),
        patch.object(c.frozen.chase, "refine", forbidden),
        patch.object(c.frozen, "compute_result", forbidden),
        patch.object(c.frozen, "t256_theorem", forbidden),
        patch.object(c.frozen.three, "compute_result", forbidden),
        patch.object(c.frozen.three, "core_zero_theorem", forbidden),
    ):
        return c.compute_result()


def test_result_reproduced_and_frozen_row_bound(result: dict[str, object]) -> None:
    assert json.loads(c.RESULT_PATH.read_bytes()) == json.loads(json.dumps(result))
    auth = c.object_row(result["AUTHORITY"])
    assert auth["FROZEN_HEAD_TREE"] == auth["FROZEN_RESULT_SHA256"] == "MATCH"
    assert auth["LEDGER_ROWS"] == 4647
    assert auth["FULL_ROWS_SHA256"] == (
        "70e2c1bb28f223566cb54799fd1b325368b90d58c5fc5001cacfbba9d2996de6"
    )
    assert (result["SOURCE_T_CAP"], result["SOURCE_S4_BASE"], result["SOURCE_ROW_BOUND"]) == (
        264,
        112,
        313391920,
    )
    assert result["PROOF_SCOPE"] == "FULL_PROFILE"
    assert result["PROVED_T_CAP"] == 255
    assert result["NEW_ADMISSIBLE_BOUND"] == 313320224
    assert result["OWNER_BOUND_DELTA"] == 71696
    assert result["UNPROVED_ASSUMPTIONS"] == []
    assert result["FAMILY_GAIN_CLAIMED"] == result["NEW_WINNING_OUTCOMES"] == 0


def test_complement_local_identity_over_all_eight_edge_patterns() -> None:
    # Summing this eight-case identity over vertex triples proves the global identity.
    for mask in range(8):
        h_edges = mask.bit_count()
        h_wedges = comb_small(h_edges, 2)
        assert int(mask == 0) == 1 - h_edges + h_wedges - int(mask == 7)
    p = c.premises()
    assert p["GOODMAN_CONSTANT"] == 299
    assert p["F_CONSTANT"] == 239
    assert p["ZETA_GE_2"] == "VERIFIED"


def comb_small(n: int, k: int) -> int:
    return sum(1 for _ in combinations(range(n), k))


def test_zero_sequences_cover_every_graph_without_a_graphicality_oracle() -> None:
    observed: set[tuple[int, ...]] = set()
    # Independent Cartesian-edge enumeration (rather than the production bit masks).
    for include in product((False, True), repeat=10):
        g_zero = [e for e, yes in zip(c.ZERO_EDGES, include, strict=True) if yes]
        zeta = tuple(sorted(6 - sum(v in e for e in g_zero) for v in range(5)))
        assert min(zeta) >= 2 and sum(zeta) >= 10 and sum(zeta) % 2 == 0
        observed.add(zeta)
    assert tuple(sorted(observed)) == c.zero_sequences()
    assert len(observed) == 31
    # Three degree-four vertices cannot coexist with two degree-zero vertices in H[Z].
    assert (2, 2, 6, 6, 6) not in observed


def test_hub_low_obstruction_counts_are_strict() -> None:
    # Each hub needs a low shadow neighbour; a shared low triple supplies at most four.
    assert 5 * (2 * 6 - (12 - 1)) == 5
    assert 2 * (2 * 1 - 1) + 2 * 1 == 4
    for q in combinations_with_replacement(range(6), 3):
        assert c.low_floor(q, 7) is not None  # the enumeration never loses a whole q class
    assert c.low_floor((5, 5, 5), 7) == 40
    assert all(c.low_floor((5, 5, 5), m) is None for m in range(7))


def test_remainder_intersection_inequality_for_all_local_neighbour_sets() -> None:
    subsets = [set(i for i in range(5) if mask & (1 << i)) for mask in range(32)]
    for a, b in product(subsets, repeat=2):
        assert len(a & b) >= max(0, len(a) + len(b) - 5)
    # For q=5, H[L]=K3: 25 core triangles plus 15 common-zero terms are disjoint.
    assert c.low_floor((5, 5, 5), 7) == 1 + 3 * (2 + 5 + 5 - 2 - 2) + 3 * (5 + 5 - 5)


def test_complete_superset_digest_and_every_branch() -> None:
    s = c.finite_superset()
    assert (s["DEGREE_CASES"], s["LOW_GRAPH_BRANCHES"], s["MAX_UPPER"]) == (1755, 6117, 255)
    assert s["COMPLETE_CASES_SHA256"] == (
        "fef1390ddbcf9c4a1b9caf6db46c0285c7cffc6de291cd1101e1f2994c92ab5d"
    )
    # Independently check each E branch, including branches that do not minimize p.
    branches = 0
    for a, b, q in product(
        combinations_with_replacement(range(2), 5),
        combinations_with_replacement(range(3), 2),
        combinations_with_replacement(range(6), 3),
    ):
        sigma = (0,) * 5 + a + b + q
        for zeta in c.zero_sequences():
            if sum(sigma) != sum(zeta) or sum(sigma) % 2:
                continue
            f = c.objective(sigma, zeta)
            for mask in range(8):
                floor = c.low_floor(q, mask)
                if floor is not None:
                    assert f - floor <= 255
                    branches += 1
    assert branches == 6117


@pytest.mark.parametrize(
    ("capacity", "remainder", "expected"),
    [(True, False, 295), (False, True, 295)],
)
def test_dropping_either_low_premise_exposes_countermodels(
    capacity: bool,
    remainder: bool,
    expected: int,
) -> None:
    relaxed = c.finite_superset(capacity=capacity, remainder=remainder)
    assert relaxed["MAX_UPPER"] == expected
    assert c.integer(relaxed["MAX_UPPER"]) > 262


def test_range_and_parity_alone_cannot_replace_the_complete_zero_graph_list() -> None:
    relaxed = c.finite_superset(tuple(combinations_with_replacement(range(2, 7), 5)))
    assert relaxed["MAX_UPPER"] == 267 > 262
    peak = c.object_row(c.rows(relaxed["MAXIMIZERS"])[0])
    assert peak["ZETA"] == [2, 2, 6, 6, 6]


@pytest.mark.parametrize(
    ("sigma", "zeta", "message"),
    [
        ((1,) + (0,) * 11 + (4, 4, 4), (2, 2, 2, 2, 4), "capacity"),
        ((0,) * 12 + (4, 4, 4), (1, 2, 2, 3, 4), "capacity"),
        ((0,) * 12 + (4, 4, 4), (2, 2, 2, 2, 2), "balance/parity"),
        ((0,) * 12 + (3, 4, 4), (2, 2, 2, 2, 3), "balance/parity"),
    ],
)
def test_invalid_capacity_balance_and_parity_are_rejected(
    sigma: tuple[int, ...],
    zeta: tuple[int, ...],
    message: str,
) -> None:
    with pytest.raises(AssertionError, match=message):
        c.objective(sigma, zeta)


def test_recorded_graph_has_exact_nonnegative_remainder(result: dict[str, object]) -> None:
    seen = c.object_row(result["RECORDED_REALIZATION"])
    t, th, f, p = (c.integer(seen[k]) for k in ("T_G", "T_H", "F", "P"))
    assert t == 299 - th == f - p <= 255
    assert min(c.integer(v) for v in c.rows(seen["P_TERMS"])) >= 0
    assert p >= c.integer(seen["LOW_P_FLOOR"])


def test_full_route_b_recount_and_source_nonmaximal_cap_term(result: dict[str, object]) -> None:
    route = c.object_row(result["ROUTE_B"])
    assert route["ARGMAX_TERM"] == (255, 313320224, 423, 201, 240786, 5067776)
    assert route["T262_TERM"] == (262, 313383152, 475, 201, 276094, 5150880)
    assert route["OLD_ARGMAX_TERM"] == (263, 313391920, 483, 201, 281526, 5162752)
    terms = cast(list[c.Term], route["ALL_T_TERMS"])
    assert len(terms) == 234
    assert [t[0] for t in terms] == list(range(22, 256))
    # The old row is not the unrefined cap-264 envelope's maximum.
    assert c.route_terms(264, 112)[-1][1] == 313401076 > c.integer(result["OLD_BOUND"])
    assert cast(c.Term, route["PRIOR_T264_TERM"])[1] == 313387988 < c.integer(result["OLD_BOUND"])


@pytest.mark.parametrize("column", [1, 2, 3, 4, 5])
def test_corrupted_route_bound_k4_contained_s4_or_s3_fails_exact_checks(column: int) -> None:
    terms = c.frozen.r32.route_b_envelope(c.PROFILE, 255, 112)
    corrupted = list(terms[-1])
    corrupted[column] += 1
    terms[-1] = cast(c.Term, tuple(corrupted))
    # Patch both evaluators equally, so the independent rational check must detect it.
    with (
        patch.object(c.frozen.r32, "route_b_envelope", return_value=terms),
        patch.object(c.frozen.split, "route_b_terms", return_value=terms),
        pytest.raises(AssertionError, match="exact rounding"),
    ):
        c.route_terms(255, 112)
