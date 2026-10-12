"""R23 complete plateau, analytic graph certificate, oracle and stop gates."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import replace
from itertools import combinations
from math import comb
from time import monotonic
from typing import cast

import pytest

from lottolab.research import b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 as r20
from lottolab.research import b649_k20_min_s2_resolved_owner_pair_refinement_r22 as r22
from lottolab.research import b649_k20_min_s2_unique_cursor_class_closure_r23 as r23
from lottolab.research.b649_k20_min_s2_dangerous_core_realizability_r5 import (
    residual_double_ticket_degrees,
    simple_graph_degree_sequence_is_graphical,
)
from lottolab.research.b649_k20_min_s2_next_active_profile_exact_bound_r8 import (
    coarse_profile_envelope,
    profile_shadow_obstruction,
)
from lottolab.research.b649_k20_min_s2_realizable_core_class_bound_r4 import (
    linear_triple_degree_sequence_passes_pair_capacity,
)

DegreeProfile = tuple[int, ...]


@pytest.fixture(scope="module")
def state() -> r23.CurrentState:
    return r23.current_state()


@pytest.fixture(scope="module")
def plateau(state: r23.CurrentState) -> r23.PlateauFrontier:
    return r23.freeze_plateau(state, deadline=monotonic() + 30)


def _artifact() -> dict[str, object]:
    return cast(dict[str, object], json.loads(r23.result_path().read_text(encoding="utf-8")))


def _independent_histogram_oracle() -> set[DegreeProfile]:
    """Solve only the 320 histogram equation, never the full profile census."""

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

    visit(6, 20, 66, 320, ())
    return profiles


def test_canonical_primitives_unique_cursor_and_zero_resolved_above(
    state: r23.CurrentState,
) -> None:
    assert r23.canonical_primitive_preflight() == {
        "STATUS": "PASS",
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "K20_S1": 372_228_640,
    }
    assert len(state.bounds) == 339
    assert r23.CURSOR_PROFILE not in state.bounds
    assert max(state.bounds.values()) == 313_653_976
    assert sum(bound > r23.START_BOUND for bound in state.bounds.values()) == 0
    assert len(state.old_owners) == 2
    assert state.input_sha256 == r23.R22_SHA256
    assert {
        r23.profile_id(p) for p, b in state.bounds.items() if b == max(state.bounds.values())
    } == {
        "66655555555511100000",
    }


@pytest.mark.parametrize(
    "key,value",
    [
        ("CURRENT_BOUND_OWNER_SET", ["66666665433111111111", "66665555555411100000"]),
        ("MAX_RESOLVED_BOUND", 313_655_321),
        ("NEXT_CURSOR_BOUND", 313_655_321),
    ],
)
def test_unique_cursor_authority_drift_fails_closed(key: str, value: object) -> None:
    result, digest = r23.committed_r22_result()
    result[key] = value
    with pytest.raises(AssertionError, match="unique-cursor authority mismatch"):
        r23.validate_current_state(result, digest)


def test_actual_ledger_contradictions_fail_even_if_summary_is_unchanged() -> None:
    result, digest = r23.committed_r22_result()
    rows = cast(list[dict[str, object]], result["FINAL_RESOLVED_LEDGER"])
    rows[0]["CURRENT_BOUND"] = r23.START_BOUND + 1
    with pytest.raises(AssertionError, match="resolved profile exceeds"):
        r23.validate_current_state(result, digest)
    rows[0]["CURRENT_BOUND"] = 313_653_976
    rows[-1] = dict(rows[0])
    with pytest.raises(AssertionError, match="duplicate committed"):
        r23.validate_current_state(result, digest)


def test_only_the_final_committed_ledger_is_read_without_owner_reconstruction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("prior owner ledger reconstruction or re-solving was invoked")

    monkeypatch.setattr(r20, "reconstruct_ledger", forbidden)
    monkeypatch.setattr(r20, "run_owner_chase", forbidden)
    monkeypatch.setattr(r22, "current_state", forbidden)
    monkeypatch.setattr(r22, "compute_result", forbidden)
    assert len(r23.current_state().bounds) == 339


def test_pinned_input_hash_rejects_working_file_substitution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def corrupt_blob(*_args: object, **_kwargs: object) -> bytes:
        return b'{"FAMILY_UPPER_BOUND":313655320}'

    monkeypatch.setattr(r23.subprocess, "check_output", corrupt_blob)
    with pytest.raises(AssertionError, match="pinned R22 result identity"):
        r23.committed_r22_result()


def test_complete_plateau_matches_independent_histogram_oracle(
    plateau: r23.PlateauFrontier,
) -> None:
    independent = _independent_histogram_oracle()
    assert set(plateau.profiles) == independent
    assert len(independent) == 69
    assert plateau.profiles == tuple(sorted(independent, reverse=True))
    assert plateau.profiles[0] == r23.CURSOR_PROFILE
    assert all(coarse_profile_envelope(p).family_upper_bound == 313_655_320 for p in independent)
    assert plateau.next_profile == r23.EXPECTED_NEXT_PROFILE
    assert plateau.next_bound == 313_652_520
    assert plateau.lookup_profile_count == plateau.complete_profiles_examined == 128
    assert plateau.square_sum_classes_examined == 2


def test_no_old_owner_rerun_or_lower_rank_work(
    state: r23.CurrentState,
    plateau: r23.PlateauFrontier,
) -> None:
    r23.assert_class_scope(state, plateau)
    for old_owner in state.old_owners:
        with pytest.raises(AssertionError, match="prior profile"):
            r23.assert_class_scope(state, replace(plateau, profiles=(old_owner,)))
    with pytest.raises(AssertionError, match="current family maximum"):
        r23.assert_class_scope(state, replace(plateau, profiles=(r23.EXPECTED_NEXT_PROFILE,)))
    with pytest.raises(AssertionError, match="duplicate"):
        r23.assert_class_scope(state, replace(plateau, profiles=(r23.CURSOR_PROFILE,) * 2))
    with pytest.raises(AssertionError, match="actual starting family maximum"):
        r23.assert_class_scope(
            replace(state, bounds={**state.bounds, (0,) * 20: r23.START_BOUND}), plateau
        )


def test_analytic_class_certificate_covers_all_realizations_and_s3_maximizers(
    plateau: r23.PlateauFrontier,
) -> None:
    certificate = r23.certify_plateau_class(plateau)
    assert certificate["CLASS_FAMILY_UPPER_BOUND"] == 313_631_576 < 313_655_320
    assert certificate["WEDGE_COUNT"] == 823
    assert certificate["INDUCED_P3_OPEN_WEDGE_LOWER_BOUND"] == 5
    assert certificate["OPEN_WEDGE_LOWER_BOUND"] == 7
    assert certificate["GRAPH_TRIANGLE_UPPER_BOUND"] == 272
    assert certificate["GRAPH_PLUS_COMPLEMENT_TRIANGLE_IDENTITY_CONSTANT"] == 289
    assert certificate["COMPLEMENT_TRIANGLE_LOWER_BOUND"] == 17
    assert certificate["NONCORE_TRIANGLE_UPPER_BOUND"] == 250
    assert certificate["SHARED_VERTEX_SUPPORT_PAIR_COUNT"] == 127
    assert certificate["TRIPLE_SUPPORT_COUNT"] == 22
    assert certificate["RESIDUAL_DOUBLE_SUPPORT_COUNT"] == 27
    assert certificate["S3_UPPER_BOUND"] == 5_241_600
    assert certificate["S4_LOWER_BOUND"] == 112
    assert certificate["FOURTH_ORDER_CREDIT"] == 64
    assert certificate["S4_FLOOR_SCOPE"] == "ALL_REALIZATIONS_INCLUDING_S3_MAXIMIZERS"
    assert certificate["COMPLETE_PLATEAU_COVERAGE"] is True
    assert certificate["PER_PROFILE_SOLVER_WORK_NEEDED"] is False
    with pytest.raises(AssertionError, match="complete unique"):
        r23.certify_plateau_class(replace(plateau, profiles=plateau.profiles[:-1]))
    with pytest.raises(AssertionError, match="dominance is insufficient"):
        r23.certify_plateau_class(replace(plateau, next_bound=313_631_576))


def test_induced_p3_class_bound_against_every_five_vertex_graph() -> None:
    pairs = tuple(combinations(range(5), 2))
    for mask in range(1 << len(pairs)):
        edges = {pair for i, pair in enumerate(pairs) if mask & (1 << i)}
        degrees = tuple(sum(vertex in edge for edge in edges) for vertex in range(5))
        triangles = sum(
            all(pair in edges for pair in combinations(triple, 2))
            for triple in combinations(range(5), 3)
        )
        floor = r23.generic_open_wedge_floor(5, len(edges), min(degrees), max(degrees))
        assert floor <= sum(comb(d, 2) for d in degrees) - 3 * triangles
        envelope = r23.graph_triangle_upper_bound_from_open_wedges(degrees, floor)
        assert envelope["GRAPH_TRIANGLE_UPPER_BOUND"] >= triangles


def _oracle_proof() -> dict[str, object]:
    artifact = _artifact()
    oracle = cast(dict[str, object], artifact["CLASS_ENVELOPE_ORACLE"])
    rows = cast(list[dict[str, object]], oracle["HISTOGRAM_ROWS"])
    return {
        "CLASS_CERTIFICATE": {
            "SQUARE_SUM": 320,
            "COMPLETE_SUFFIX_ENUMERATION": True,
            "PROFILE_IDENTITIES": artifact["CURRENT_LOAD_BEARING_PLATEAU"],
            "HISTOGRAM_ENVELOPES": [
                {
                    "PROFILE": [int(d) for d in cast(str, row["PROFILE_ID"])],
                    "RELAXATION_STATUS": row["STATUS"],
                    "LOWER_BOUND_SOURCE": row["LOWER_BOUND_SOURCE"],
                    "WEIGHTED_OPEN_WEDGE_LOWER_BOUND": row["OPEN_WEDGE_LOWER_BOUND"],
                    "SOLVER_WALL_TIME_SECONDS": row["SOLVER_SECONDS"],
                    "FAMILY_UPPER_BOUND": row["FAMILY_UPPER_BOUND"],
                }
                for row in rows
            ],
            "CLASS_FAMILY_UPPER_BOUND": oracle["CLASS_FAMILY_UPPER_BOUND"],
            "GRAPH_TRIANGLE_UPPER_BOUND": oracle["GRAPH_TRIANGLE_UPPER_BOUND"],
        },
        "NATIVE_CLASS_DEADLINE_SECONDS": 600.0,
        "EXTERNAL_TIMEOUT_SECONDS": 620.0,
    }


def test_observed_native_class_oracle_covers_every_frozen_profile(
    plateau: r23.PlateauFrontier,
) -> None:
    oracle = r23.validate_class_oracle(_oracle_proof(), plateau, r23.EXPECTED_CLASS_BOUND)
    assert oracle["STATUS"] == "PASS"
    assert oracle["HISTOGRAM_COUNT"] == 69
    assert oracle["COMPLETE_PLATEAU_COVERAGE"] is True
    assert oracle["ORACLE_USED_TO_SET_CLOSURE_BOUND"] is False
    assert cast(int, oracle["CLASS_FAMILY_UPPER_BOUND"]) <= 313_631_576


def test_class_oracle_rejects_incumbents_missing_members_and_false_bounds(
    plateau: r23.PlateauFrontier,
) -> None:
    proof = _oracle_proof()
    certificate = cast(dict[str, object], proof["CLASS_CERTIFICATE"])
    rows = cast(list[dict[str, object]], certificate["HISTOGRAM_ENVELOPES"])
    rows[0]["RELAXATION_STATUS"] = "FEASIBLE"
    rows[0]["LOWER_BOUND_SOURCE"] = "OPTIMAL_OBJECTIVE_VALUE"
    with pytest.raises(AssertionError, match="certified best bound"):
        r23.validate_class_oracle(proof, plateau, r23.EXPECTED_CLASS_BOUND)
    rows[0]["LOWER_BOUND_SOURCE"] = "BEST_OBJECTIVE_BOUND_FLOOR"
    assert r23.validate_class_oracle(proof, plateau, r23.EXPECTED_CLASS_BOUND)["STATUS"] == "PASS"
    missing = copy.deepcopy(proof)
    missing_certificate = cast(dict[str, object], missing["CLASS_CERTIFICATE"])
    cast(list[object], missing_certificate["HISTOGRAM_ENVELOPES"]).pop()
    with pytest.raises(AssertionError, match="membership is incomplete"):
        r23.validate_class_oracle(missing, plateau, r23.EXPECTED_CLASS_BOUND)
    rows[0]["FAMILY_UPPER_BOUND"] = cast(int, rows[0]["FAMILY_UPPER_BOUND"]) + 1
    with pytest.raises(AssertionError, match="does not reproduce"):
        r23.validate_class_oracle(proof, plateau, r23.EXPECTED_CLASS_BOUND)


def test_immediate_stop_when_prior_resolved_owners_return(
    monkeypatch: pytest.MonkeyPatch,
    state: r23.CurrentState,
) -> None:
    events: list[str] = []
    recompute = r23.recompute_family_bound

    def oracle(
        active: r23.CurrentState, frozen: r23.PlateauFrontier, *, deadline: float
    ) -> dict[str, object]:
        assert deadline > monotonic()
        r23.assert_class_scope(active, frozen)
        events.append("CLASS_ORACLE_AT_START_MAXIMUM")
        return _oracle_proof()

    def transition(
        prior: Mapping[DegreeProfile, int],
        *,
        class_profiles: tuple[DegreeProfile, ...],
        class_bound: int,
        next_profile: DegreeProfile,
        next_bound: int,
    ) -> tuple[int, tuple[DegreeProfile, ...]]:
        assert prior == state.bounds
        events.append("RECOMPUTE_AND_STOP_AT_RESOLVED_OWNER")
        return recompute(
            prior,
            class_profiles=class_profiles,
            class_bound=class_bound,
            next_profile=next_profile,
            next_bound=next_bound,
        )

    monkeypatch.setattr(r23, "run_class_oracle", oracle)
    monkeypatch.setattr(r23, "recompute_family_bound", transition)
    monkeypatch.setattr(r23, "solver_runtime_preflight", lambda: {"STATUS": "PASS"})
    result = r23.compute_result()
    assert events == ["CLASS_ORACLE_AT_START_MAXIMUM", "RECOMPUTE_AND_STOP_AT_RESOLVED_OWNER"]
    assert result["TASK_STATUS"] == r23.SUCCESS_C
    assert result["CURRENT_BOUND_OWNER_SET"] == list(r23.EXPECTED_RESOLVED_OWNERS)
    assert result["PROFILE_COUNT_PROCESSED"] == 0
    assert result["WORK_AFTER_RESOLVED_OWNER_RETURNED"] is False


def test_real_result_family_max_retains_all_resolved_and_class_bounds(
    state: r23.CurrentState,
    plateau: r23.PlateauFrontier,
) -> None:
    result = _artifact()
    family, owners = r23.recompute_family_bound(
        state.bounds,
        class_profiles=plateau.profiles,
        class_bound=313_631_576,
        next_profile=r23.EXPECTED_NEXT_PROFILE,
        next_bound=313_652_520,
    )
    assert family == result["END_BOUND"] == result["FAMILY_UPPER_BOUND"] == 313_653_976
    assert tuple(map(r23.profile_id, owners)) == r23.EXPECTED_RESOLVED_OWNERS
    assert result["TASK_STATUS"] == r23.SUCCESS_C
    assert result["CURRENT_PLATEAU_PROFILE_COUNT"] == 69
    assert result["CURRENT_LOAD_BEARING_PLATEAU"] == list(map(r23.profile_id, plateau.profiles))
    assert result["CURRENT_PLATEAU_COMPLETELY_RESOLVED"] is True
    assert result["PLATEAU_COUNT_PROCESSED"] == result["CLASSES_ANALYZED"] == 1
    assert result["CLASSES_CERTIFIED"] == 1
    assert result["PROFILES_ELIMINATED_BY_CLASS_BOUND"] == 69
    assert result["PROFILE_COUNT_PROCESSED"] == result["PRIOR_PROFILE_RERUN_COUNT"] == 0
    assert result["SOLVER_PROFILES_SENT"] == []
    assert result["CERTIFIED_FAMILY_DROP"] == 1_344
    assert result["REMAINING_GAP"] == 414_315
    assert result["NEXT_ACTIVE_BOUND"] == 313_652_520
    assert result["NEXT_ACTIVE_PROFILE"] == "66666665432211111111"
    assert result["NEXT_ACTIVE_CURSOR_IS_LOAD_BEARING"] is False
    assert result["CURRENT_BOUND_OWNER_ROLE"] == "PREVIOUSLY_RESOLVED_PROFILE"
    assert result["STOP_REASON"] == "PREVIOUSLY_RESOLVED_PROFILE_BECAME_OWNER"
    assert result["PACKET_SUCCESS_A_SATISFIED"] is False
    assert result["PACKET_SUCCESS_B_SATISFIED"] is False
    assert result["PACKET_SUCCESS_C_SATISFIED"] is True
    assert result["PRIOR_OWNER_LEDGER_REBUILT"] is False
    assert result["FULL_4850_PROFILE_CENSUS_REBUILT"] is False
    assert result["WORK_BELOW_CURRENT_FAMILY_MAX_STARTED"] is False
    assert result["WORK_AFTER_RESOLVED_OWNER_RETURNED"] is False
    assert result["NEW_PORTFOLIO_SEARCH_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == "NONE"
    runtime = cast(dict[str, object], result["SOLVER_RUNTIME_PREFLIGHT"])
    assert runtime["STATUS"] == result["CANONICAL_PRIMITIVE_STATUS"] == "PASS"
    assert runtime["PYTHON_VERSION"] == "3.13.8"
    assert runtime["ORTOOLS_VERSION"] == "9.15.6755"
    assert runtime["EXTERNAL_TIMEOUT_PROBE_EXIT_CODE"] == 124
    limits = cast(dict[str, object], result["SOLVER_CONFIGURED_WALL_LIMIT"])
    assert limits["CP_SAT_SEARCH_WORKERS"] == 1
    assert limits["PROOF_WALL_SECONDS"] == 3600.0
    assert limits["MAX_SUCCESSIVE_PLATEAUS"] == 3
    assert limits["MAX_NEW_PROFILE_SOLVES"] == 64
    oracle = cast(dict[str, object], result["CLASS_ENVELOPE_ORACLE"])
    assert oracle["STATUS"] == "PASS"
    assert oracle["EXTERNAL_TIMEOUT_EXIT_CODE"] == 0
    assert result["SOLVER_CERTIFIED_BOUND"] == oracle["CLASS_FAMILY_UPPER_BOUND"]
    assert result["SOLVER_CERTIFIED_BOUND_SCOPE"] == "CURRENT_PLATEAU_CLASS_ONLY"
    assert result["CLASS_ORACLE_HISTOGRAM_RELAXATIONS"] == 69
    assert result["EXACT_SUPPORT_PROFILE_SOLVES"] == 0
    assert result["MAX_RESOLVED_PROFILE_BOUND"] == 313_653_976
