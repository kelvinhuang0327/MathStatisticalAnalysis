"""Independent graph/class oracles and exact R18 cursor/scope regressions."""

from __future__ import annotations

import json
from dataclasses import replace
from itertools import combinations
from math import comb
from time import monotonic
from typing import cast

import pytest

import lottolab.research.b649_k20_min_s2_cursor_plateau_closure_r18 as r18
from lottolab.research.b649_k20_min_s2_class_dominance_or_descent_r13 import (
    graph_triangle_upper_bound_from_open_wedges,
)
from lottolab.research.b649_k20_min_s2_current_bound_owner_refinement_r15 import (
    canonical_primitive_preflight,
)
from lottolab.research.b649_k20_min_s2_dangerous_core_realizability_r5 import (
    residual_double_ticket_degrees,
    simple_graph_degree_sequence_is_graphical,
)
from lottolab.research.b649_k20_min_s2_next_active_profile_exact_bound_r8 import (
    coarse_profile_envelope,
    profile_shadow_obstruction,
)
from lottolab.research.b649_k20_min_s2_r16_freeze_and_owner_refinement_r17 import (
    EXPECTED_NEXT_CURSOR_PROFILE,
    EXPECTED_OWNER_PROFILE,
)
from lottolab.research.b649_k20_min_s2_realizable_core_class_bound_r4 import (
    linear_triple_degree_sequence_passes_pair_capacity,
)

DegreeProfile = tuple[int, ...]


def _artifact() -> dict[str, object]:
    return cast(dict[str, object], json.loads(r18.result_path().read_text(encoding="utf-8")))


def _independent_square_sum_class() -> set[DegreeProfile]:
    """Enumerate only the 324 histogram equation, independent of the rank iterator."""

    profiles: set[DegreeProfile] = set()

    def visit(degree: int, slots: int, total: int, squares: int, prefix: DegreeProfile) -> None:
        if total < 0 or squares < 0 or total > degree * slots or squares > degree * total:
            return
        if degree == 0:
            if total == squares == 0:
                candidate = (*prefix, *((0,) * slots))
                if (
                    linear_triple_degree_sequence_passes_pair_capacity(candidate, 22)
                    and simple_graph_degree_sequence_is_graphical(
                        residual_double_ticket_degrees(candidate)
                    )
                    and profile_shadow_obstruction(candidate) is None
                ):
                    profiles.add(candidate)
            return
        for count in range(min(slots, total // degree, squares // (degree * degree)) + 1):
            visit(
                degree - 1,
                slots - count,
                total - degree * count,
                squares - degree * degree * count,
                (*prefix, *((degree,) * count)),
            )

    visit(6, 20, 66, 324, ())
    return profiles


def test_canonical_primitives_and_r17_override() -> None:
    assert canonical_primitive_preflight() == {
        "STATUS": "PASS",
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "K20_S1": 372_228_640,
    }
    state = r18.current_state()
    assert len(state.bounds) == 227
    assert state.bounds[EXPECTED_OWNER_PROFILE] == 313_662_376
    assert state.sources[EXPECTED_OWNER_PROFILE] == "R17.OWNER_REFINED_BOUND"
    assert max(state.bounds.values()) == 313_671_448
    assert state.cursor == EXPECTED_NEXT_CURSOR_PROFILE
    assert state.cursor_bound == 313_672_792
    assert state.cursor not in state.bounds


def test_r17_cursor_and_owner_bound_drift_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    original = cast(
        dict[str, object], json.loads(r18.result_path(r18.R17_RESULT_FILENAME).read_text())
    )
    for key, value in (
        ("NEXT_CURSOR_PROFILE", "66666665443111111110"),
        ("OWNER_REFINED_BOUND", 313_674_248),
    ):
        changed = {**original, key: value}

        def read_changed(_path: object, value: dict[str, object] = changed) -> dict[str, object]:
            return value

        monkeypatch.setattr(r18, "_read_object", read_changed)
        with pytest.raises(AssertionError, match="R17 authority mismatch"):
            r18.current_state()


def test_plateau_membership_matches_independent_histogram_oracle() -> None:
    plateau = r18.freeze_plateau(r18.current_state(), deadline=monotonic() + 30)
    independent = _independent_square_sum_class()
    assert set(plateau.profiles) == independent
    assert len(independent) == 55
    assert plateau.profiles[0] == EXPECTED_NEXT_CURSOR_PROFILE
    assert all(
        coarse_profile_envelope(p).family_upper_bound == r18.START_BOUND for p in independent
    )
    assert plateau.next_profile == r18.EXPECTED_NEXT_PROFILE
    assert plateau.next_bound == 313_658_120
    assert plateau.complete_profiles_examined == 64
    assert plateau.square_sum_classes_examined == 2
    assert plateau.lookup_profile_count == 64


def test_no_old_owner_or_below_maximum_solver_requests() -> None:
    state = r18.current_state()
    plateau = r18.freeze_plateau(state, deadline=monotonic() + 30)

    def guard(requested: tuple[DegreeProfile, ...], active_bound: int = r18.START_BOUND) -> None:
        r18.assert_plateau_only_scope(
            requested, prior=state.bounds, plateau=plateau.profiles, active_bound=active_bound
        )

    guard(plateau.profiles)
    for old_profile in (
        EXPECTED_OWNER_PROFILE,
        *(tuple(int(d) for d in identity) for identity in r18.EXPECTED_BOUND_OWNERS),
    ):
        with pytest.raises(AssertionError, match="prior profile"):
            guard((old_profile,))
    with pytest.raises(AssertionError, match="frozen current-plateau"):
        guard((r18.EXPECTED_NEXT_PROFILE,))
    with pytest.raises(AssertionError, match="duplicate"):
        guard((state.cursor, state.cursor))
    with pytest.raises(AssertionError, match="current family maximum"):
        guard((state.cursor,), active_bound=r18.START_BOUND + 1)


def test_clique_partitions_exclude_93_edges_and_require_rounding_to_six() -> None:
    assert r18.clique_partition_edge_totals(20, 6, 12) == (
        ((7, 13), 99),
        ((8, 12), 94),
        ((9, 11), 91),
        ((10, 10), 90),
    )
    assert r18.generic_open_wedge_floor(20, 93, 6, 12) == 5
    assert r18.generic_open_wedge_floor(20, 94, 6, 12) == 0
    envelope = graph_triangle_upper_bound_from_open_wedges(
        tuple(6 + degree for degree in EXPECTED_NEXT_CURSOR_PROFILE), 5
    )
    assert envelope == {
        "WEDGE_COUNT": 825,
        "OPEN_WEDGE_LOWER_BOUND": 6,
        "GRAPH_TRIANGLE_UPPER_BOUND": 273,
    }


def test_generic_class_triangle_envelope_covers_every_five_vertex_graph() -> None:
    pairs = tuple(combinations(range(5), 2))
    for mask in range(1 << len(pairs)):
        edges = {pair for i, pair in enumerate(pairs) if mask & (1 << i)}
        degrees = tuple(sum(vertex in edge for edge in edges) for vertex in range(5))
        triangles = sum(
            all(pair in edges for pair in combinations(triple, 2))
            for triple in combinations(range(5), 3)
        )
        open_wedges = sum(comb(degree, 2) for degree in degrees) - 3 * triangles
        floor = r18.generic_open_wedge_floor(5, len(edges), min(degrees), max(degrees))
        assert floor <= open_wedges
        envelope = graph_triangle_upper_bound_from_open_wedges(degrees, floor)
        assert envelope["GRAPH_TRIANGLE_UPPER_BOUND"] >= triangles


def test_induced_p3_injection_on_dense_noncluster_graph() -> None:
    edges = set(combinations(range(8), 2)) - {(0, 1)}
    degree = tuple(sum(vertex in edge for edge in edges) for vertex in range(8))
    triangles = sum(
        all(pair in edges for pair in combinations(triple, 2))
        for triple in combinations(range(8), 3)
    )
    observed_open = sum(comb(d, 2) for d in degree) - 3 * triangles
    assert min(degree) == 6
    assert r18.generic_open_wedge_floor(8, len(edges), min(degree), max(degree)) == 5
    assert observed_open == 6


def test_one_certificate_covers_all_realizations_and_s3_maximizers() -> None:
    plateau = r18.freeze_plateau(r18.current_state(), deadline=monotonic() + 30)
    certificate = r18.certify_plateau_class(plateau)
    assert certificate["CLASS_FAMILY_UPPER_BOUND"] == 313_649_048 < r18.EXPECTED_NEXT_BOUND
    assert certificate["COMPLEMENT_TRIANGLE_LOWER_BOUND"] == 18
    assert certificate["GRAPH_TRIANGLE_UPPER_BOUND"] == 273
    assert certificate["SHARED_VERTEX_SUPPORT_PAIR_COUNT"] == 129
    assert certificate["TRIPLE_SUPPORT_COUNT"] == 22
    assert certificate["RESIDUAL_DOUBLE_SUPPORT_COUNT"] == 27
    assert certificate["S4_LOWER_BOUND"] == 112
    assert certificate["FOURTH_ORDER_CREDIT"] == 64
    assert certificate["S4_FLOOR_SCOPE"] == "ALL_REALIZATIONS_INCLUDING_S3_MAXIMIZERS"
    assert certificate["PER_PROFILE_SOLVER_WORK_NEEDED"] is False
    with pytest.raises(AssertionError, match="complete square-sum"):
        r18.certify_plateau_class(replace(plateau, profiles=plateau.profiles[:-1]))
    with pytest.raises(AssertionError, match="below its successor"):
        r18.certify_plateau_class(replace(plateau, next_bound=313_649_048))


def test_family_max_keeps_prior_owners_and_all_class_envelopes() -> None:
    state = r18.current_state()
    plateau = r18.freeze_plateau(state, deadline=monotonic() + 30)

    def recompute(class_bound: int) -> tuple[int, tuple[DegreeProfile, ...]]:
        return r18.recompute_family_bound(
            state.bounds,
            class_profiles=plateau.profiles,
            class_bound=class_bound,
            next_profile=r18.EXPECTED_NEXT_PROFILE,
            next_bound=r18.EXPECTED_NEXT_BOUND,
        )

    family, owners = recompute(313_649_048)
    assert family == 313_671_448 > r18.EXPECTED_NEXT_BOUND
    assert tuple(r18.profile_identity(p) for p in owners) == r18.EXPECTED_BOUND_OWNERS
    higher_class, class_owners = recompute(r18.START_BOUND + 1)
    assert higher_class == r18.START_BOUND + 1
    assert set(class_owners) == set(plateau.profiles)


def test_committed_result_accounts_for_solver_budget_and_owner_handoff() -> None:
    result = _artifact()
    assert result["TASK_STATUS"] == "SUCCESS_C_PLATEAU_RESOLVED_EXACT_LOAD_BEARING_CURSOR"
    assert result["BASE_HEAD"] == r18.BASE_HEAD
    assert result["BASE_TREE"] == r18.BASE_TREE
    assert result["START_BOUND"] == 313_672_792
    assert (
        result["PLATEAU_COUNT_PROCESSED"]
        == result["CLASSES_ANALYZED"]
        == result["CLASSES_CERTIFIED"]
        == 1
    )
    assert (
        result["CURRENT_PLATEAU_PROFILE_COUNT"]
        == result["PROFILES_ELIMINATED_BY_CLASS_BOUND"]
        == 55
    )
    assert result["PROFILE_COUNT_PROCESSED"] == result["PRIOR_PROFILE_RERUN_COUNT"] == 0
    assert result["SOLVER_PROFILES_SENT"] == []
    assert result["FAMILY_UPPER_BOUND"] == 313_671_448
    assert result["INCUMBENT"] == 313_239_661
    assert result["REMAINING_GAP"] == 431_787
    assert result["CERTIFIED_FAMILY_DROP"] == 1_344
    assert result["NEXT_ACTIVE_PROFILE"] == "66666665442111111111"
    assert result["NEXT_ACTIVE_BOUND"] == 313_658_120
    assert result["NEXT_ACTIVE_CURSOR_IS_LOAD_BEARING"] is False
    assert result["NEXT_ACTIVE_PROFILE_ROLE"] == "UNRESOLVED_RANKED_PREFIX"
    assert result["CURRENT_PLATEAU_COMPLETELY_RESOLVED"] is True
    assert result["PACKET_SUCCESS_A_SATISFIED"] is False
    assert result["PACKET_SUCCESS_B_SATISFIED"] is False
    assert result["PACKET_SUCCESS_C_SATISFIED"] is True
    assert result["NEW_LOAD_BEARING_CURSOR_PROFILE"] == "66666555554411100000"
    assert result["NEW_LOAD_BEARING_CURSOR_BOUND"] == result["FAMILY_UPPER_BOUND"]
    assert result["NEW_LOAD_BEARING_CURSOR_SOURCE"] == "R11.PROFILE_BOUNDS[15]"
    assert result["NEW_LOAD_BEARING_CURSOR_TIED_PROFILES"] == list(r18.EXPECTED_BOUND_OWNERS)
    new_cursor = tuple(int(d) for d in cast(str, result["NEW_LOAD_BEARING_CURSOR_PROFILE"]))
    state = r18.current_state()
    assert new_cursor != state.cursor
    assert state.bounds[new_cursor] == max(state.bounds.values()) == result["FAMILY_UPPER_BOUND"]
    assert result["CURRENT_BOUND_OWNERS"] == list(r18.EXPECTED_BOUND_OWNERS)
    assert result["CURRENT_BOUND_OWNER_SOURCES"] == {
        "66666555554411100000": "R11.PROFILE_BOUNDS[15]",
        "66665555555421000000": "R11.PROFILE_BOUNDS[17]",
    }
    assert result["PRIOR_RESOLVED_OWNER_REUSED_BOUND"] == 313_662_376
    assert result["CANONICAL_PRIMITIVE_STATUS"] == "PASS"
    runtime = cast(dict[str, object], result["SOLVER_RUNTIME_PREFLIGHT"])
    assert runtime["STATUS"] == "PASS"
    assert runtime["EXTERNAL_TIMEOUT_PROBE_EXIT_CODE"] == 124
    oracle = cast(dict[str, object], result["CLASS_ENVELOPE_ORACLE"])
    assert oracle["STATUS"] == "PASS"
    assert oracle["HISTOGRAM_COUNT"] == 55
    assert oracle["ORACLE_USED_TO_SET_CLOSURE_BOUND"] is False
    assert result["SOLVER_CERTIFIED_BOUND"] == oracle["CLASS_FAMILY_UPPER_BOUND"] == 313_589_688
    assert result["ANALYTIC_CLASS_CERTIFIED_BOUND"] == 313_649_048
    assert result["FULL_4850_PROFILE_CENSUS_REBUILT"] is False
    assert result["WORK_BELOW_CURRENT_FAMILY_MAX_STARTED"] is False
    assert result["NEW_PORTFOLIO_SEARCH_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == "NONE"


def _oracle_proof_from_artifact() -> dict[str, object]:
    oracle = cast(dict[str, object], _artifact()["CLASS_ENVELOPE_ORACLE"])
    rows: list[dict[str, object]] = []
    for encoded in cast(list[str], oracle["HISTOGRAM_ROWS"]):
        profile, status, wall, floor, _triangle, bound = encoded.split("|")
        rows.append(
            {
                "PROFILE": [int(d) for d in profile],
                "RELAXATION_STATUS": status,
                "LOWER_BOUND_SOURCE": "OPTIMAL_OBJECTIVE_VALUE",
                "SOLVER_WALL_TIME_SECONDS": float(wall),
                "WEIGHTED_OPEN_WEDGE_LOWER_BOUND": int(floor),
                "FAMILY_UPPER_BOUND": int(bound),
            }
        )
    return {
        "CLASS_CERTIFICATE": {
            "SQUARE_SUM": 324,
            "COMPLETE_SUFFIX_ENUMERATION": True,
            "HISTOGRAM_ENVELOPES": rows,
            "CLASS_FAMILY_UPPER_BOUND": oracle["CLASS_FAMILY_UPPER_BOUND"],
            "GRAPH_TRIANGLE_UPPER_BOUND": oracle["GRAPH_TRIANGLE_UPPER_BOUND"],
        }
    }


def test_oracle_rejects_missing_members_and_feasible_incumbent_objectives() -> None:
    proof = _oracle_proof_from_artifact()
    certificate = cast(dict[str, object], proof["CLASS_CERTIFICATE"])
    rows = cast(list[dict[str, object]], certificate["HISTOGRAM_ENVELOPES"])
    rows[0]["RELAXATION_STATUS"] = "FEASIBLE"
    with pytest.raises(AssertionError, match="certified best bound"):
        r18.attach_class_oracle(_artifact(), proof)
    rows[0]["LOWER_BOUND_SOURCE"] = "BEST_OBJECTIVE_BOUND_FLOOR"
    result = _artifact()
    r18.attach_class_oracle(result, proof)
    assert result["SOLVER_CERTIFIED_BOUND"] == 313_589_688
    rows.pop()
    with pytest.raises(AssertionError, match="membership is incomplete"):
        r18.attach_class_oracle(_artifact(), proof)
