"""Resume-cursor and certificate checks for the R12 K20 S2 descent."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict
from itertools import combinations
from pathlib import Path
from typing import Any

import pytest

from lottolab.research.b649_k20_min_s2_continued_multi_plateau_descent_r12 import (
    CERTIFIED_DROP_TARGET,
    EXPECTED_ORTOOLS_VERSION,
    EXPECTED_PYTHON_VERSION,
    INCUMBENT,
    PREVIOUS_PROFILE_COUNT,
    PREVIOUS_RESULT_PATH,
    PROFILE_CAP,
    START_BOUND,
    START_PROFILE,
    assert_no_prior_profile_rerun,
    compact_descent_result,
    lookup_ranked_frontier,
    solver_runtime_preflight,
    validate_resume_cursor,
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

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RESULT_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "research"
    / "matrix-native-results"
    / "b649-k20-min-s2-continued-multi-plateau-descent-r12-result.json"
)


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _prior_profiles() -> frozenset[tuple[int, ...]]:
    return validate_resume_cursor(_read(PREVIOUS_RESULT_PATH))


def _decode_rows(encoded: str) -> tuple[tuple[int, ...], ...]:
    if not encoded:
        return ()
    return tuple(tuple(int(value) for value in row.split(",")) for row in encoded.split(";"))


def _graph_triangle_count(
    triples: Sequence[Sequence[int]], doubles: Sequence[Sequence[int]]
) -> int:
    edges = {
        tuple(sorted(pair)) for support in (*triples, *doubles) for pair in combinations(support, 2)
    }
    return sum(
        all(tuple(sorted(pair)) in edges for pair in combinations(triangle, 2))
        for triangle in combinations(range(20), 3)
    )


def test_resume_cursor_regression_starts_at_r11_next_profile() -> None:
    previous = _read(PREVIOUS_RESULT_PATH)
    prior_profiles = validate_resume_cursor(previous)
    frontier = lookup_ranked_frontier(profile_limit=4)

    assert len(prior_profiles) == PREVIOUS_PROFILE_COUNT == 24
    assert START_BOUND == previous["NEXT_ACTIVE_BOUND"] == 313_716_136
    assert tuple(previous["NEXT_ACTIVE_PROFILE"]) == START_PROFILE
    assert frontier.profiles[0] == START_PROFILE
    assert frontier.envelopes[0].family_upper_bound == START_BOUND
    assert START_PROFILE not in prior_profiles
    assert not prior_profiles.intersection(frontier.profiles)
    keys = tuple(
        (
            envelope.family_upper_bound,
            envelope.s3_upper_bound,
            envelope.wedge_count,
            profile,
        )
        for profile, envelope in zip(frontier.profiles, frontier.envelopes, strict=True)
    )
    assert keys == tuple(sorted(keys, reverse=True))
    assert frontier.complete_profiles_examined < 4_850


def test_resume_cursor_guard_rejects_a_previously_resolved_profile() -> None:
    previous = _read(PREVIOUS_RESULT_PATH)
    prior_profiles = validate_resume_cursor(previous)
    wrong_cursor = tuple(previous["PROFILE_BOUNDS"][0]["PROFILE"])

    with pytest.raises(AssertionError, match="cursor"):
        validate_resume_cursor(previous, start_profile=wrong_cursor)
    with pytest.raises(AssertionError, match="prior profile again"):
        assert_no_prior_profile_rerun(prior_profiles, (wrong_cursor,))
    assert_no_prior_profile_rerun(prior_profiles, (START_PROFILE,))


def test_solver_runtime_preflight_matches_the_locked_research_runtime() -> None:
    result = solver_runtime_preflight()

    assert result["STATUS"] == "PASS"
    assert result["PYTHON_VERSION"] == EXPECTED_PYTHON_VERSION == "3.13.8"
    assert result["ORTOOLS_VERSION"] == EXPECTED_ORTOOLS_VERSION == "9.15.6755"
    assert result["CP_MODEL_IMPORT"] == "PASS"
    assert result["EXTERNAL_TIMEOUT_PROBE_EXIT_CODE"] == 124
    assert "GNU coreutils" in str(result["EXTERNAL_TIMEOUT_WRAPPER_VERSION"])


def test_result_records_stop_condition_frontier_and_no_reruns() -> None:
    result = _read(RESULT_PATH)
    previous_profiles = _prior_profiles()
    profile_items = result["PROFILE_BOUNDS"]
    profile_ids = tuple(tuple(item["PROFILE"]) for item in profile_items)
    profile_count = result["PROFILE_COUNT_PROCESSED"]

    assert result["TASK_ID"] == "B649_K20_MIN_S2_CONTINUED_MULTI_PLATEAU_DESCENT_R12"
    assert result["BASE_HEAD"] == "c1dbcffe9c8aa11e643dcf4b4e30dee1ca40ff2b"
    assert result["BASE_TREE"] == "9d105fd2605c80d233e8428ae4387cac98b8ff6b"
    assert result["TASK_BRANCH"] == "codex/b649-k20-min-s2-continued-multi-plateau-descent-r12"
    assert result["TASK_STATUS"] in {
        "SUCCESS_A_FAMILY_CLOSED",
        "SUCCESS_B_CERTIFIED_DROP",
        "SUCCESS_C_PROFILE_CAP",
        "SUCCESS_C_PROOF_WALL_BUDGET",
    }
    assert result["START_BOUND"] == START_BOUND
    assert result["END_BOUND"] == result["FAMILY_UPPER_BOUND"]
    assert result["CUMULATIVE_ADDITIONAL_DROP"] == START_BOUND - result["END_BOUND"]
    assert result["PROFILE_COUNT_PROCESSED"] == result["ACTUAL_PROFILE_COUNT"]
    assert profile_count == len(profile_items) == result["ADDITIONAL_PROFILE_COUNT"]
    assert len(set(profile_ids)) == len(profile_ids)
    assert not previous_profiles.intersection(profile_ids)
    assert result["PRIOR_RESOLVED_PROFILE_COUNT"] == 24
    assert result["PRIOR_PROFILE_RERUN_COUNT"] == 0
    assert result["TOTAL_RESOLVED_PROFILE_COUNT"] == 24 + profile_count
    assert result["PLATEAU_COUNT_PROCESSED"] == len(
        dict.fromkeys(item["RANKED_COARSE_BOUND"] for item in profile_items)
    )
    assert result["RANK_LOOKUP"]["FULL_4850_PROFILE_RANKING_RERUN"] is False
    assert result["RANK_LOOKUP"]["COMPLETE_PROFILES_EXAMINED"] < 4_850
    assert result["NEW_PORTFOLIO_SEARCH_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == "NONE"
    assert result["SOLVER_RUNTIME_PREFLIGHT"]["STATUS"] == "PASS"
    assert result["SOLVER_CERTIFIED_BOUND"] == result["FAMILY_UPPER_BOUND"]
    assert result["SOLVER_CONFIGURED_WALL_LIMIT"]["PROOF_WALL_BUDGET_SECONDS"] == 3_600.0
    assert (
        result["SOLVER_CONFIGURED_WALL_LIMIT"]["EXTERNAL_HARD_TIMEOUT_SECONDS_PER_PROFILE"] == 90.0
    )
    assert result["SOLVER_CONFIGURED_WALL_LIMIT"]["WORKERS"] == 1

    next_profile = result["NEXT_ACTIVE_PROFILE"]
    next_bound = result["NEXT_ACTIVE_BOUND"]
    if next_profile is not None:
        assert coarse_profile_envelope(tuple(next_profile)).family_upper_bound == next_bound
    if result["TASK_STATUS"] == "SUCCESS_A_FAMILY_CLOSED":
        assert result["FAMILY_UPPER_BOUND"] <= INCUMBENT
        assert result["FAMILY_STATUS"] == "CLOSED"
    elif result["TASK_STATUS"] == "SUCCESS_B_CERTIFIED_DROP":
        assert result["CUMULATIVE_ADDITIONAL_DROP"] >= CERTIFIED_DROP_TARGET
    elif result["TASK_STATUS"] == "SUCCESS_C_PROFILE_CAP":
        assert profile_count == PROFILE_CAP
    else:
        assert result["SOLVER_ACTUAL_WALL_TIME_SECONDS"] >= 3_600.0


def test_recorded_profile_realizations_and_motif_envelopes_are_certified() -> None:
    result = _read(RESULT_PATH)
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
        assert item["SUPPORT_SOLVER_STATUS"] in {"FEASIBLE", "OPTIMAL"}
        triples = _decode_rows(item["WITNESS_TRIPLES"])
        doubles = _decode_rows(item["WITNESS_DOUBLE_SUPPORTS"])
        assert len(triples) == K20_TRIPLE_SUPPORT_COUNT == 22
        assert len(doubles) == K20_DOUBLE_SUPPORT_COUNT == 27
        signature = validate_k20_support_realization(triples, doubles, profile)
        assert item["WITNESS_MOTIFS"] == asdict(signature)

        motif = item["MOTIF_SOLVER"]
        degree_class = item["DEGREE_CLASS_RELAXATION"]
        assert motif["SOLVER_STATUS"] in {"FEASIBLE", "OPTIMAL"}
        assert degree_class["SOLVER_STATUS"] in {"FEASIBLE", "OPTIMAL"}
        motif_triples = _decode_rows(motif["MOTIF_WITNESS_TRIPLES"])
        motif_doubles = _decode_rows(motif["MOTIF_WITNESS_DOUBLE_SUPPORTS"])
        validate_k20_support_realization(motif_triples, motif_doubles, profile)
        witness_triangles = _graph_triangle_count(motif_triples, motif_doubles)
        assert witness_triangles == motif["WITNESS_GRAPH_TRIANGLE_COUNT"]
        motif_bound = motif["SOLVER_CERTIFIED_TRIANGLE_UPPER_BOUND"]
        assert motif_bound >= witness_triangles

        coarse = coarse_profile_envelope(profile)
        triangle_bound = min(
            coarse.graph_triangle_upper_bound,
            motif_bound,
            degree_class["GRAPH_TRIANGLE_UPPER_BOUND"],
        )
        assert item["GRAPH_TRIANGLE_UPPER_BOUND"] == triangle_bound
        s3_bound = s3_sum_from_wedges_and_triangles(
            coarse.wedge_count, triangle_bound - K20_TRIPLE_SUPPORT_COUNT
        )
        s4_lower_bound = max(
            K20_REUSED_S4_LOWER_BOUND,
            SEVEN_INACTIVE_TICKET_S4_LOWER_BOUND if profile.count(0) == 7 else 0,
        )
        assert item["S4_LOWER_BOUND"] == s4_lower_bound
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
    item = json.loads(json.dumps(compact))["PROFILE_BOUNDS"][0]

    assert item["WITNESS_TRIPLES"] == "0,1,2"
    assert item["WITNESS_DOUBLE_SUPPORTS"] == "3,4"
    assert _decode_rows(item["WITNESS_TRIPLES"]) == ((0, 1, 2),)
    assert item["MOTIF_SOLVER"]["MOTIF_WITNESS_TRIPLES"] == "5,6,7"
    assert item["MOTIF_SOLVER"]["MOTIF_WITNESS_DOUBLE_SUPPORTS"] == "8,9"
