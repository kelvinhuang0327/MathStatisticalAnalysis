"""Focused checks for the R14 successive class-dominance certificate."""

from __future__ import annotations

import importlib
import json
from collections import defaultdict
from itertools import combinations
from math import comb
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
from typing import Any, cast

import pytest

import lottolab.research.b649_k20_min_s2_class_dominance_or_descent_r13 as r13
from lottolab.research.b649_k20_min_s2_class_dominance_or_descent_r13 import (
    assert_no_prior_profile_rerun,
    degree_class_open_wedge_relaxation,
    graph_triangle_upper_bound_from_open_wedges,
)
from lottolab.research.b649_k20_min_s2_successive_class_dominance_r14 import (
    INCUMBENT,
    MINIMUM_SQUARE_SUM,
    PRIOR_RESOLVED_PROFILE_COUNT,
    START_BOUND,
    START_PROFILE,
    assert_ranked_frontier_invariant,
    canonical_primitive_preflight,
    coarse_family_bound_for_square_sum,
    lookup_ranked_frontier,
    validate_prior_frontier_state,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RESULT_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "research"
    / "matrix-native-results"
    / "b649-k20-min-s2-successive-class-dominance-r14-result.json"
)


def _triangle_count(edges: set[tuple[int, int]], vertex_count: int) -> int:
    return sum(
        all(tuple(sorted(pair)) in edges for pair in combinations(triangle, 2))
        for triangle in combinations(range(vertex_count), 3)
    )


def _read_result() -> dict[str, object]:
    decoded: object = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    if not isinstance(decoded, dict):
        raise AssertionError("R14 result must be a JSON object")
    return cast(dict[str, object], decoded)


def _require_int(record: dict[str, object], key: str) -> int:
    value = record.get(key)
    if type(value) is not int:
        raise AssertionError(f"{key} must be an integer")
    return value


def _require_str(record: dict[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str):
        raise AssertionError(f"{key} must be text")
    return value


def _decode_profile_identities(certificate: dict[str, object]) -> tuple[tuple[int, ...], ...]:
    raw = certificate.get("PROFILE_IDENTITIES")
    if not isinstance(raw, list):
        raise AssertionError("class certificate lacks profile identities")
    identities: list[tuple[int, ...]] = []
    for identity in cast(list[object], raw):
        if not isinstance(identity, str) or len(identity) != 20:
            raise AssertionError("compact profile identity must contain twenty digits")
        if any(character not in "0123456" for character in identity):
            raise AssertionError("compact profile identity contains a degree outside 0..6")
        identities.append(tuple(int(character) for character in identity))
    return tuple(identities)


def test_canonical_primitives_and_no_rerun_guard_cover_all_76_profiles() -> None:
    assert canonical_primitive_preflight() == {
        "STATUS": "PASS",
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "K20_S1": 372_228_640,
    }
    prior = validate_prior_frontier_state()
    assert len(prior.profiles) == PRIOR_RESOLVED_PROFILE_COUNT == 76
    assert prior.active_bound == START_BOUND
    assert prior.active_profile == START_PROFILE
    assert START_PROFILE not in prior.profiles
    with pytest.raises(AssertionError, match="prior profile again"):
        assert_no_prior_profile_rerun(prior.profiles, (next(iter(prior.profiles)),))


def test_ranked_frontier_starts_at_r13_cursor_and_keeps_order() -> None:
    prior = validate_prior_frontier_state()
    frontier = lookup_ranked_frontier(
        start_profile=START_PROFILE,
        start_square_sum=sum(degree**2 for degree in START_PROFILE),
        profile_limit=5,
        deadline=monotonic() + 30,
        prior_profiles=prior.profiles,
    )

    assert frontier.profiles[0] == START_PROFILE
    assert len(frontier.profiles) == len(set(frontier.profiles)) == 5
    assert not prior.profiles.intersection(frontier.profiles)
    assert frontier.complete_profiles_examined < 4_850
    assert 0 < frontier.square_sum_classes_examined < 56
    assert not frontier.lookup_complete
    assert_ranked_frontier_invariant(frontier.profiles, frontier.envelopes)


def test_coarse_class_envelope_is_monotone_and_matches_r13_frontier() -> None:
    assert coarse_family_bound_for_square_sum(334) == 313_698_664
    assert coarse_family_bound_for_square_sum(332) == START_BOUND
    previous_bound = START_BOUND
    for square_sum in range(332, MINIMUM_SQUARE_SUM - 1, -2):
        family_bound = coarse_family_bound_for_square_sum(square_sum)
        assert family_bound <= previous_bound
        previous_bound = family_bound


def test_relaxed_class_triangle_envelope_covers_all_small_graphs() -> None:
    vertex_count = 5
    pairs = tuple(combinations(range(vertex_count), 2))
    observed: dict[tuple[int, ...], list[int]] = defaultdict(lambda: [10**9, -1])
    for mask in range(1 << len(pairs)):
        edges = {pair for index, pair in enumerate(pairs) if mask & (1 << index)}
        degrees = tuple(sum(vertex in pair for pair in edges) for vertex in range(vertex_count))
        wedges = sum(comb(degree, 2) for degree in degrees)
        triangles = _triangle_count(edges, vertex_count)
        open_wedges = wedges - 3 * triangles
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


def test_feasible_solver_status_uses_only_best_bound_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cp_model = cast(Any, importlib.import_module("ortools.sat.python.cp_model"))

    class FeasibleSolver:
        def __init__(self) -> None:
            self.parameters = SimpleNamespace()

        def Solve(self, model: object) -> int:
            del model
            return cp_model.FEASIBLE

        def StatusName(self, status: int) -> str:
            del status
            return "FEASIBLE"

        def BestObjectiveBound(self) -> float:
            return 7.9

        def WallTime(self) -> float:
            return 0.001

    def fake_import_module(_name: str) -> Any:
        return cp_model

    monkeypatch.setattr(r13, "import_module", fake_import_module)
    monkeypatch.setattr(cp_model, "CpSolver", FeasibleSolver)
    relaxation = degree_class_open_wedge_relaxation((1, 1, 2), wall_limit_seconds=1.0)

    assert relaxation["SOLVER_STATUS"] == "FEASIBLE"
    assert relaxation["WEIGHTED_OPEN_WEDGE_LOWER_BOUND"] == 7


def test_compact_result_records_class_bounds_and_bounded_fallback() -> None:
    result = _read_result()
    prior = validate_prior_frontier_state()
    certificates_raw = result.get("CLASS_CERTIFICATES")
    if not isinstance(certificates_raw, list):
        raise AssertionError("R14 result lacks class certificates")
    certificates = cast(list[dict[str, object]], certificates_raw)
    certified = [
        item
        for item in certificates
        if item.get("CERTIFICATION_STATUS")
        in {"CERTIFIED_BELOW_ACTIVE_BOUND", "CERTIFIED_EMPTY_BY_STRUCTURAL_FILTERS"}
    ]
    class_profiles = {profile for item in certified for profile in _decode_profile_identities(item)}

    assert result["BASE_HEAD"] == "b48cc8bfe197b80201e1c57c55a8dcce4d17dae2"
    assert result["START_BOUND"] == START_BOUND
    assert result["INCUMBENT"] == INCUMBENT
    assert result["PRIOR_RESOLVED_PROFILE_COUNT"] == PRIOR_RESOLVED_PROFILE_COUNT
    assert result["PRIOR_PROFILE_RERUN_COUNT"] == 0
    assert result["NO_RERUN_GUARD_STATUS"] == "PASS"
    assert result["CLASS_ENVELOPE_ORACLE_STATUS"] == "PASS"
    assert result["RANKED_FRONTIER_INVARIANT_STATUS"] == "PASS"
    assert _require_str(result, "TASK_STATUS").startswith("SUCCESS_")
    fallback_count = _require_int(result, "FALLBACK_PROFILE_COUNT")
    fallback_resolved_count = _require_int(result, "FALLBACK_PROFILE_RESOLVED_COUNT")
    assert fallback_count <= 72
    assert fallback_resolved_count <= fallback_count
    assert _require_int(result, "CLASSES_ANALYZED") == len(certificates)
    assert _require_int(result, "CLASSES_CERTIFIED") == len(certified)
    assert not class_profiles.intersection(prior.profiles)
    assert _require_int(result, "PROFILES_ELIMINATED_BY_CLASS_BOUND") == len(class_profiles)
    assert _require_int(result, "TOTAL_RESOLVED_PROFILE_COUNT") == (
        PRIOR_RESOLVED_PROFILE_COUNT + len(class_profiles) + fallback_resolved_count
    )
    square_sums = [_require_int(item, "SQUARE_SUM") for item in certificates]
    assert square_sums == sorted(square_sums, reverse=True)
    for certificate in certificates:
        assert certificate["COMPLETE_SUFFIX_ENUMERATION"] is True
        rows_raw = certificate.get("HISTOGRAM_ENVELOPES", [])
        if not isinstance(rows_raw, list):
            raise AssertionError("compact histogram rows must be an array")
        for row_raw in cast(list[object], rows_raw):
            if not isinstance(row_raw, str):
                raise AssertionError("compact histogram row must be text")
            fields = row_raw.split("|")
            assert len(fields) == 11
            if fields[1] == "FEASIBLE":
                assert fields[4] == "BEST_OBJECTIVE_BOUND_FLOOR"
                assert fields[3].isdigit()
    assert result["NEW_PORTFOLIO_SEARCH_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == "NONE"
    assert result["FULL_4850_PROFILE_CENSUS_REBUILT"] is False
