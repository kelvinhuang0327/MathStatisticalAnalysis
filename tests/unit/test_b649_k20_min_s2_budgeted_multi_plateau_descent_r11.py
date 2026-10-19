"""Focused frontier and certificate checks for the R11 K20 S2 descent."""

from __future__ import annotations

import json
from collections.abc import Sequence
from itertools import combinations
from pathlib import Path
from typing import Any

from lottolab.research.b649_k20_min_s2_budgeted_multi_plateau_descent_r11 import (
    CERTIFIED_DROP_TARGET,
    INCUMBENT,
    PROFILE_CAP,
    START_BOUND,
    START_PROFILE,
    compact_descent_result,
    group_ranked_plateaus,
    lookup_ranked_frontier,
)
from lottolab.research.b649_k20_min_s2_dangerous_core_realizability_r5 import (
    K20_DOUBLE_SUPPORT_COUNT,
    K20_REUSED_S4_LOWER_BOUND,
    K20_TRIPLE_SUPPORT_COUNT,
    validate_k20_support_realization,
)
from lottolab.research.b649_k20_min_s2_next_active_profile_exact_bound_r8 import (
    coarse_profile_envelope,
    profile_shadow_obstruction,
)
from lottolab.research.b649_k20_min_s2_next_distinct_plateau_r10 import (
    SEVEN_INACTIVE_TICKET_S4_LOWER_BOUND,
)
from lottolab.research.b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_S1,
    K20_S2,
    s3_sum_from_wedges_and_triangles,
)

RESULT_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "research"
    / "matrix-native-results"
    / "b649-k20-min-s2-budgeted-multi-plateau-descent-r11-result.json"
)


def _decode_rows(encoded: str) -> tuple[tuple[int, ...], ...]:
    if not encoded:
        return ()
    return tuple(
        tuple(int(value) for value in row.split(","))
        for row in encoded.split(";")
    )


def _graph_triangle_count(
    triples: Sequence[Sequence[int]],
    doubles: Sequence[Sequence[int]],
) -> int:
    edges = {
        tuple(sorted(pair))
        for support in (*triples, *doubles)
        for pair in combinations(support, 2)
    }
    return sum(
        all(tuple(sorted(pair)) in edges for pair in combinations(triangle, 2))
        for triangle in combinations(range(20), 3)
    )


def _read_result() -> dict[str, Any]:
    return json.loads(RESULT_PATH.read_text(encoding="utf-8"))


def test_ranked_frontier_preserves_order_and_groups_equal_bounds() -> None:
    frontier = lookup_ranked_frontier(profile_limit=PROFILE_CAP + 1)
    groups = group_ranked_plateaus(frontier.profiles)
    keys = tuple(
        (
            envelope.family_upper_bound,
            envelope.s3_upper_bound,
            envelope.wedge_count,
            profile,
        )
        for profile, envelope in zip(frontier.profiles, frontier.envelopes, strict=True)
    )

    assert frontier.profiles[0] == START_PROFILE
    assert frontier.envelopes[0].family_upper_bound == START_BOUND
    assert keys == tuple(sorted(keys, reverse=True))
    assert tuple((bound, len(profiles)) for bound, profiles in groups) == (
        (313_733_608, 9),
        (313_718_936, 10),
        (313_716_136, 6),
    )
    assert frontier.profiles[24] == (
        6,
        6,
        6,
        6,
        6,
        6,
        6,
        4,
        4,
        4,
        4,
        3,
        3,
        2,
        0,
        0,
        0,
        0,
        0,
        0,
    )
    assert all(bound < 313_736_408 for bound, _ in groups)
    assert frontier.complete_profiles_examined < 4_850


def test_result_reaches_a_declared_stop_with_an_exact_next_frontier() -> None:
    result = _read_result()
    profile_count = result["PROFILE_COUNT_PROCESSED"]

    assert result["TASK_ID"] == "B649_K20_MIN_S2_BUDGETED_MULTI_PLATEAU_DESCENT_R11"
    assert result["BASE_HEAD"] == "906deaa00504601068bdae06583042f28c230f19"
    assert result["BASE_TREE"] == "68e4bba672918c6810aa08da5ee9939acb29b55a"
    assert result["TASK_STATUS"] in (
        "SUCCESS_A_FAMILY_CLOSED",
        "SUCCESS_B_CERTIFIED_DROP",
        "SUCCESS_C_PROFILE_CAP",
        "SUCCESS_C_PROOF_WALL_BUDGET",
    )
    assert result["START_BOUND"] == START_BOUND
    assert result["END_BOUND"] == result["FAMILY_UPPER_BOUND"]
    assert result["CUMULATIVE_DROP"] == START_BOUND - result["END_BOUND"]
    assert result["CUMULATIVE_DROP"] >= 0
    assert profile_count == result["ACTUAL_PROFILE_COUNT"]
    assert profile_count == (
        result["UNREALIZABLE_PROFILE_COUNT"] + result["REALIZABLE_PROFILE_COUNT"]
    )
    assert profile_count <= PROFILE_CAP
    assert result["PROFILE_CAP"] <= PROFILE_CAP
    assert result["PLATEAU_COUNT_PROCESSED"] > 0
    assert result["RANK_LOOKUP"]["FULL_4850_PROFILE_RANKING_RERUN"] is False
    assert result["RANK_LOOKUP"]["COMPLETE_PROFILES_EXAMINED"] < 4_850
    assert result["NEW_PORTFOLIO_SEARCH_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == "NONE"

    next_profile = result["NEXT_ACTIVE_PROFILE"]
    next_bound = result["NEXT_ACTIVE_BOUND"]
    if next_profile is not None:
        envelope = coarse_profile_envelope(tuple(next_profile))
        assert envelope.family_upper_bound == next_bound
        if result["PROFILE_BOUNDS"]:
            previous_bound = result["PROFILE_BOUNDS"][-1]["RANKED_COARSE_BOUND"]
            assert next_bound <= previous_bound
    if result["TASK_STATUS"] == "SUCCESS_B_CERTIFIED_DROP":
        assert result["CUMULATIVE_DROP"] >= CERTIFIED_DROP_TARGET
    if result["TASK_STATUS"] == "SUCCESS_A_FAMILY_CLOSED":
        assert result["FAMILY_UPPER_BOUND"] <= INCUMBENT
    if result["TASK_STATUS"] == "SUCCESS_C_PROFILE_CAP":
        assert profile_count == PROFILE_CAP


def test_recorded_profile_realizations_and_motif_envelopes_are_certified() -> None:
    result = _read_result()
    for item in result["PROFILE_BOUNDS"]:
        profile = tuple(item["PROFILE"])
        if item["REALIZABILITY"] == "UNREALIZABLE":
            obstruction = item.get("SHADOW_OBSTRUCTION")
            if obstruction is not None:
                assert profile_shadow_obstruction(profile) is not None
                assert item["SUPPORT_SOLVER_STATUS"] == "NOT_RUN_SHADOW_OBSTRUCTION"
            else:
                assert item["SUPPORT_SOLVER_STATUS"] == "INFEASIBLE"
                assert item["FAMILY_UPPER_BOUND"] is None
            continue

        assert item["REALIZABILITY"] == "REALIZABLE"
        assert item["SUPPORT_SOLVER_STATUS"] in ("FEASIBLE", "OPTIMAL")
        triples = tuple(
            tuple(row) for row in _decode_rows(item["WITNESS_TRIPLES"])
        )
        doubles = tuple(
            tuple(row) for row in _decode_rows(item["WITNESS_DOUBLE_SUPPORTS"])
        )
        assert len(triples) == K20_TRIPLE_SUPPORT_COUNT
        assert len(doubles) == K20_DOUBLE_SUPPORT_COUNT == 27
        signature = validate_k20_support_realization(triples, doubles, profile)
        assert item["WITNESS_MOTIFS"] == {
            field: getattr(signature, field) for field in signature.__dataclass_fields__
        }

        motif = item["MOTIF_SOLVER"]
        degree_class = item["DEGREE_CLASS_RELAXATION"]
        assert motif["SOLVER_STATUS"] in ("FEASIBLE", "OPTIMAL")
        assert degree_class["SOLVER_STATUS"] in ("FEASIBLE", "OPTIMAL")
        motif_triples = tuple(
            tuple(row) for row in _decode_rows(motif["MOTIF_WITNESS_TRIPLES"])
        )
        motif_doubles = tuple(
            tuple(row)
            for row in _decode_rows(motif["MOTIF_WITNESS_DOUBLE_SUPPORTS"])
        )
        validate_k20_support_realization(motif_triples, motif_doubles, profile)
        witness_triangle_count = _graph_triangle_count(motif_triples, motif_doubles)
        assert witness_triangle_count == motif["WITNESS_GRAPH_TRIANGLE_COUNT"]
        motif_bound = motif["SOLVER_CERTIFIED_TRIANGLE_UPPER_BOUND"]
        assert motif_bound >= witness_triangle_count

        coarse = coarse_profile_envelope(profile)
        triangle_bound = min(
            coarse.graph_triangle_upper_bound,
            motif_bound,
            degree_class["GRAPH_TRIANGLE_UPPER_BOUND"],
        )
        assert item["GRAPH_TRIANGLE_UPPER_BOUND"] == triangle_bound
        s4_lower_bound = (
            SEVEN_INACTIVE_TICKET_S4_LOWER_BOUND
            if profile.count(0) == 7
            else K20_REUSED_S4_LOWER_BOUND
        )
        assert item["S4_LOWER_BOUND"] == s4_lower_bound
        s3_bound = s3_sum_from_wedges_and_triangles(
            coarse.wedge_count, triangle_bound - K20_TRIPLE_SUPPORT_COUNT
        )
        assert item["S3_UPPER_BOUND"] == s3_bound
        assert item["FAMILY_UPPER_BOUND"] == (
            K20_S1 - K20_S2 + s3_bound - (4 * s4_lower_bound) // 7
        )
        assert item["FAMILY_UPPER_BOUND"] <= item["COARSE_FAMILY_UPPER_BOUND"]


def test_compact_serializer_round_trips_support_rows() -> None:
    compact = compact_descent_result(
        {
            "PROFILE_BOUNDS": [
                {
                    "REALIZABILITY": "REALIZABLE",
                    "WITNESS_TRIPLES": [[0, 1, 2]],
                    "WITNESS_DOUBLE_SUPPORTS": [[3, 4]],
                    "MOTIF_SOLVER": {
                        "MOTIF_WITNESS_TRIPLES": [[5, 6, 7]],
                        "MOTIF_WITNESS_DOUBLE_SUPPORTS": [[8, 9]],
                    },
                }
            ]
        }
    )
    decoded = json.loads(json.dumps(compact))
    item = decoded["PROFILE_BOUNDS"][0]

    assert item["WITNESS_TRIPLES"] == "0,1,2"
    assert item["WITNESS_DOUBLE_SUPPORTS"] == "3,4"
    assert _decode_rows(item["WITNESS_TRIPLES"]) == ((0, 1, 2),)
    assert item["MOTIF_SOLVER"]["MOTIF_WITNESS_TRIPLES"] == "5,6,7"
