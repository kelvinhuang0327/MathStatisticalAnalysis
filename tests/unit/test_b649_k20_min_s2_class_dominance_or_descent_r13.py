"""Focused guards and small oracle for the K20 S2 R13 class certificate."""

from __future__ import annotations

import json
from collections import defaultdict
from itertools import combinations
from math import comb
from pathlib import Path
from time import monotonic
from typing import Any

import pytest

from lottolab.research.b649_k20_min_s2_class_dominance_or_descent_r13 import (
    BASE_HEAD,
    BASE_TREE,
    INCUMBENT,
    R12_RESULT_PATH,
    RESULT_PATH,
    START_BOUND,
    START_PROFILE,
    TASK_BRANCH,
    TASK_ID,
    assert_no_prior_profile_rerun,
    degree_class_open_wedge_relaxation,
    graph_triangle_upper_bound_from_open_wedges,
    lookup_ranked_frontier,
    profile_family_envelope_from_triangle_bound,
    validate_prior_resolved_state,
)
from lottolab.research.b649_k20_min_s2_dangerous_core_realizability_r5 import (
    K20_REUSED_S4_LOWER_BOUND,
)
from lottolab.research.b649_k20_min_s2_higher_order_closure_r2 import K20_S1, K20_S2
from lottolab.research.b649_k20_min_s2_realizable_core_class_bound_r4 import (
    s3_sum_from_wedges_and_triangles,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _triangle_count(edges: set[tuple[int, int]], vertex_count: int) -> int:
    return sum(
        all(tuple(sorted(pair)) in edges for pair in combinations(triangle, 2))
        for triangle in combinations(range(vertex_count), 3)
    )


def test_no_rerun_guard_and_exact_r12_cursor() -> None:
    prior = validate_prior_resolved_state()
    r12 = _read(R12_RESULT_PATH)
    certificate = _read(RESULT_PATH)["CLASS_DOMINANCE_CERTIFICATE"]
    candidates = tuple(tuple(profile) for profile in certificate["PROFILE_IDENTITIES"])

    assert prior.profile_count == 72
    assert len(prior.profiles) == 72
    assert tuple(r12["NEXT_ACTIVE_PROFILE"]) == START_PROFILE
    assert START_PROFILE not in prior.profiles
    assert len(candidates) == 4
    assert not prior.profiles.intersection(candidates)
    assert_no_prior_profile_rerun(prior.profiles, candidates)
    with pytest.raises(AssertionError, match="prior profile again"):
        assert_no_prior_profile_rerun(prior.profiles, (next(iter(prior.profiles)),))


def test_ranked_frontier_starts_at_cursor_and_preserves_exact_order() -> None:
    prior = validate_prior_resolved_state()
    frontier = lookup_ranked_frontier(
        profile_limit=5,
        deadline=monotonic() + 30,
        prior_profiles=prior.profiles,
    )
    keys = tuple(
        (
            envelope.family_upper_bound,
            envelope.s3_upper_bound,
            envelope.wedge_count,
            envelope.degree_profile,
        )
        for envelope in frontier.envelopes
    )

    assert frontier.profiles[0] == START_PROFILE
    square_sums = tuple(sum(degree**2 for degree in profile) for profile in frontier.profiles)
    assert square_sums == (334, 334, 334, 334, 332)
    for square_sum in set(square_sums):
        class_profiles = tuple(
            profile
            for profile in frontier.profiles
            if sum(degree**2 for degree in profile) == square_sum
        )
        assert class_profiles == tuple(sorted(class_profiles, reverse=True))
    assert keys == tuple(sorted(keys, reverse=True))
    assert not prior.profiles.intersection(frontier.profiles)
    assert frontier.square_sum_classes_examined == 2
    assert frontier.complete_profiles_examined == 5
    assert not frontier.lookup_complete
    assert frontier.complete_profiles_examined < 4_850


def test_coarse_bound_is_monotone_through_every_lower_square_sum_class() -> None:
    previous_bound = START_BOUND
    bounds: dict[int, int] = {}
    for square_sum in range(334, 221, -2):
        wedge_count = (square_sum + 11 * 66 + 30 * 20) // 2
        noncore_triangle_bound = wedge_count // 3 - 22
        s3_bound = s3_sum_from_wedges_and_triangles(wedge_count, noncore_triangle_bound)
        fourth_order_credit = (4 * K20_REUSED_S4_LOWER_BOUND) // 7
        family_bound = K20_S1 - K20_S2 + s3_bound - fourth_order_credit
        assert family_bound <= previous_bound
        bounds[square_sum] = family_bound
        previous_bound = family_bound

    assert bounds[334] == START_BOUND
    assert bounds[332] == 313_695_864


def test_degree_class_open_wedge_relaxation_matches_small_graph_oracle() -> None:
    vertex_count = 5
    pairs = tuple(combinations(range(vertex_count), 2))
    observed: dict[tuple[int, ...], list[int]] = defaultdict(lambda: [10**9, -1])
    for mask in range(1 << len(pairs)):
        edges = {pair for index, pair in enumerate(pairs) if mask & (1 << index)}
        degrees = tuple(sum(vertex in pair for pair in edges) for vertex in range(vertex_count))
        wedge_count = sum(comb(degree, 2) for degree in degrees)
        triangles = _triangle_count(edges, vertex_count)
        open_wedges = wedge_count - 3 * triangles
        summary = observed[degrees]
        summary[0] = min(summary[0], open_wedges)
        summary[1] = max(summary[1], triangles)

    for degrees, (minimum_open_wedges, maximum_triangles) in observed.items():
        relaxation = degree_class_open_wedge_relaxation(degrees, wall_limit_seconds=2.0)
        assert relaxation["SOLVER_STATUS"] == "OPTIMAL"
        lower_bound = relaxation["WEIGHTED_OPEN_WEDGE_LOWER_BOUND"]
        assert isinstance(lower_bound, int)
        assert lower_bound <= minimum_open_wedges
        envelope = graph_triangle_upper_bound_from_open_wedges(degrees, lower_bound)
        assert envelope["GRAPH_TRIANGLE_UPPER_BOUND"] >= maximum_triangles


def test_profile_motif_envelope_reuses_s3_and_s4_certificates() -> None:
    envelope = profile_family_envelope_from_triangle_bound(START_PROFILE, 271)

    assert envelope == {
        "WEDGE_COUNT": 830,
        "GRAPH_TRIANGLE_UPPER_BOUND": 271,
        "NONCORE_TRIANGLE_UPPER_BOUND": 249,
        "S3_UPPER_BOUND": 5_249_328,
        "S4_LOWER_BOUND": 112,
        "FOURTH_ORDER_CREDIT": 64,
        "FAMILY_UPPER_BOUND": 313_639_304,
        "COARSE_FAMILY_UPPER_BOUND": START_BOUND,
    }
    assert envelope["FAMILY_UPPER_BOUND"] > INCUMBENT


def test_compact_result_certifies_only_the_remaining_square_sum_suffix() -> None:
    result = _read(RESULT_PATH)
    certificate = result["CLASS_DOMINANCE_CERTIFICATE"]
    profiles = tuple(tuple(profile) for profile in certificate["PROFILE_IDENTITIES"])
    bounds = tuple(row["FAMILY_UPPER_BOUND"] for row in certificate["HISTOGRAM_ENVELOPES"])

    assert result["TASK_ID"] == TASK_ID
    assert result["TASK_STATUS"] == "SUCCESS_C_CLASS_DOMINANCE"
    assert result["BASE_HEAD"] == BASE_HEAD
    assert result["BASE_TREE"] == BASE_TREE
    assert result["TASK_BRANCH"] == TASK_BRANCH
    assert result["START_BOUND"] == START_BOUND
    assert result["END_BOUND"] == result["FAMILY_UPPER_BOUND"] == 313_695_864
    assert result["CUMULATIVE_DROP"] == 2_800
    assert result["CLASS_LOCAL_DROP"] == 59_360
    assert result["PRIOR_RESOLVED_PROFILE_COUNT"] == 72
    assert result["PRIOR_PROFILE_RERUN_COUNT"] == 0
    assert result["PROFILES_ELIMINATED_BY_CLASS_BOUND"] == 4
    assert result["FALLBACK_PROFILE_COUNT"] == 0
    assert result["TOTAL_RESOLVED_PROFILE_COUNT"] == 76
    assert certificate["SQUARE_SUM"] == 334
    assert certificate["WEDGE_COUNT"] == 830
    assert certificate["COMPLETE_SUFFIX_ENUMERATION"] is True
    assert certificate["CLASS_FAMILY_UPPER_BOUND"] == 313_639_304
    assert certificate["HIGHER_RANK_PROFILE_BOUND"] == 313_689_592
    assert certificate["CLASS_FAMILY_UPPER_BOUND"] < certificate["HIGHER_RANK_PROFILE_BOUND"]
    assert len(profiles) == len(set(profiles)) == len(bounds) == 4
    assert max(bounds) == certificate["CLASS_FAMILY_UPPER_BOUND"]
    assert result["NEXT_ACTIVE_BOUND"] == 313_695_864
    assert result["NEXT_ACTIVE_PROFILE"] == [
        6,
        6,
        6,
        6,
        6,
        6,
        6,
        5,
        4,
        4,
        4,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        0,
        0,
    ]
    assert result["SOLVER_RUNTIME_PREFLIGHT"]["STATUS"] == "PASS"
    assert result["RANK_LOOKUP"]["FULL_4850_PROFILE_RANKING_RERUN"] is False
    assert result["NEW_PORTFOLIO_SEARCH_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == "NONE"
