"""Owner dispatch, complete envelope coverage, and exact certificate replay."""

from __future__ import annotations

import json
import math
from fractions import Fraction
from itertools import product
from typing import Any, cast

import pytest

from lottolab.research import b649_k20_r3_state_tail_owner_chase_r14 as r14


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(r14.RESULT_PATH.read_text(encoding="utf-8")))


def _chase(*, drop_target: int = 10, state_limit: int = 8) -> r14.Chase:
    return r14.Chase(
        states=(("state:a", 100), ("state:b", 98)),
        baseline=1_000,
        next_loss=901,
        classified_maximum=("classified-vector", 90),
        start_bound=100,
        r4_reference=0,
        drop_target=drop_target,
        state_limit=state_limit,
    )


def _eliminated(counts: r14.CountVector, loss: int) -> r14.r13.ClassifiedVector:
    return r14.r13.ClassifiedVector(
        vector_id=f"synthetic-vector:{loss}",
        counts=counts,
        local_loss=loss,
        status=r14.r12.ELIMINATED,
        pair_union_penalty=None,
        forest_floor=None,
        r6_correction=None,
        four_ticket_status=None,
        four_ticket_penalty=None,
        correction=None,
        vector_bound=None,
        witness=None,
    )


def test_canonical_primitives_and_current_owner_selection() -> None:
    assert r14.canonical_primitives() == {
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "PAIR_INTERSECTION_COST[6]": 18_611_432,
        "K20_S1": 372_228_640,
    }
    authority = r14.authority()
    chase = r14.Chase(
        states=r14.initial_state_terms(),
        baseline=r14.r12.canonical_uncorrected_baseline(),
        next_loss=r14.START_LOSS,
        classified_maximum=(
            str(authority["MAX_CLASSIFIED_VECTOR_ID"]),
            int(authority["MAX_CLASSIFIED_VECTOR_BOUND"]),
        ),
    )
    assert len(chase.states) == 23
    assert chase.owners == ("state:s2-12695020-s3-735532",)
    assert chase.bound == 356_799_210
    assert chase.state_max - chase.tail_bound == 26
    assert chase.states[0][0] != chase.owners[0]


def test_state_tail_switch_immediately_stops_the_previous_owner() -> None:
    chase = _chase()
    assert chase.owners == ("state:a",)
    chase.improve_state("state:a", {"new_bound": 80})
    assert chase.owners == (r14.TAIL_ID,)
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        chase.improve_state("state:a", {"new_bound": 70})
    chase.advance_tail(901, ((0,),), 903, lambda counts: _eliminated(counts, 901))
    assert chase.owners == ("state:b",)
    assert chase.tail_bound == 97 < chase.state_max == 98
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        chase.advance_tail(903, ((0,),), 904, lambda counts: _eliminated(counts, 903))
    chase.improve_state("state:b", {"new_bound": 79})
    assert chase.owners == (r14.TAIL_ID,)
    assert [event["to"] for event in chase.events] == [[r14.TAIL_ID], ["state:b"], [r14.TAIL_ID]]


def test_non_owner_state_is_rejected_before_any_certificate_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(_: str) -> None:
        raise RuntimeError("certificate recovery was called for a non-owner")

    monkeypatch.setattr(r14, "owner_region", forbidden)
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r14.certify_state(_chase(), "state:b", use_solvers=False)


def test_tail_tie_cannot_descend_below_state_threshold() -> None:
    chase = _chase()
    chase.next_loss = 900
    assert set(chase.owners) == {"state:a", r14.TAIL_ID}
    with pytest.raises(AssertionError, match="tail descent below"):
        chase.advance_tail(900, ((0,),), 901, lambda counts: _eliminated(counts, 900))


def test_tied_state_improvement_recomputes_the_other_owner() -> None:
    chase = _chase()
    chase.states = (("state:a", 100), ("state:b", 100))
    chase.improve_state("state:a", {"new_bound": 80})
    assert chase.bound == 100
    assert chase.owners == ("state:b",)
    assert chase.events[-1]["from"] == ["state:a", "state:b"]


def test_success_b_stops_before_any_additional_tail_work() -> None:
    chase = _chase(drop_target=5)
    chase.improve_state("state:a", {"new_bound": 80})
    chase.advance_tail(901, ((0,),), 903, lambda counts: _eliminated(counts, 901))
    chase.improve_state("state:b", {"new_bound": 79})
    chase.advance_tail(903, ((0,),), 905, lambda counts: _eliminated(counts, 903))
    assert chase.bound == 95
    assert chase.stop_condition() == r14.STOP_B
    with pytest.raises(AssertionError, match="stop condition"):
        chase.advance_tail(905, ((0,),), 906, lambda counts: _eliminated(counts, 905))


def test_eight_state_limit_finishes_only_the_required_tail_transition() -> None:
    chase = _chase(state_limit=1)
    chase.improve_state("state:a", {"new_bound": 80})
    assert chase.stop_condition() is None
    chase.advance_tail(901, ((0,),), 903, lambda counts: _eliminated(counts, 901))
    assert chase.stop_condition() == r14.STOP_C
    assert chase.owners == ("state:b",)
    with pytest.raises(AssertionError, match=r"stop condition|batch boundary"):
        chase.improve_state("state:b", {"new_bound": 79})


def test_rational_multiplicity_dual_against_small_exhaustive_histograms() -> None:
    for cap in range(2, 6):
        for histogram in product(range(4), repeat=cap + 1):
            pair_mass = sum(math.comb(m, 2) * count for m, count in enumerate(histogram))
            correction = sum(max(m - 1, 0) * count for m, count in enumerate(histogram))
            assert r14.rational_correction(pair_mass, cap) <= correction
    assert r14.rational_correction(44_903_012) == 4_989_224
    with pytest.raises(ValueError):
        r14.rational_correction(-1)


def test_state_envelope_covers_dominated_members_and_all_compressed_vectors(
    result: dict[str, Any],
) -> None:
    for record in cast(list[dict[str, Any]], result["STATE_OWNER_CERTIFICATES"]):
        region = r14.owner_region(str(record["owner_id"]))
        threshold = int(record["active_competing_state_threshold"])
        refined = cast(list[dict[str, Any]], record["region_moment_certificates"])
        relevant = tuple(row for row in region if r14.raw_bound(row) >= threshold)
        carried = tuple(row for row in region if r14.raw_bound(row) < threshold)
        assert len(region) == record["region_compressed_state_count"]
        assert (
            sum(row.represented_vector_count for row in region)
            == record["region_type_vector_count"]
        )
        assert len(relevant) == len(refined) == record["refined_region_member_count"]
        assert len(carried) == record["carried_region_member_count"]
        assert (
            r14.digest(tuple((row.witness_counts, r14.raw_bound(row)) for row in region))
            == record["region_sha256"]
        )
        assert max(r14.raw_bound(row) for row in carried) == record["carried_region_maximum"]
        assert record["new_bound"] == max(
            record["carried_region_maximum"], record["refined_region_maximum"]
        )
        # A witness-only replacement would miss nonmaximizing members still
        # above the competing state. They must be covered by the owner proof.
        assert any(r14.raw_bound(row) < record["prior_bound"] for row in relevant)
        for state, row in zip(relevant, refined, strict=True):
            certificate = cast(dict[str, Any], row["certificate"])
            assert state.represented_vector_count == 1
            assert certificate == r14.moment_certificate(state.witness_counts)
            expected = (
                r14.joint_constant()
                - state.anchor_pair_s2
                + state.anchor_triple_s3
                - max(state.applied_residual_union_penalty, certificate["correction_lower_bound"])
            )
            assert row["certified_bound"] == expected <= row["raw_bound"]
        support = tuple(tuple(int(label) for label in row) for row in record["support_witness"])
        maximizing = min(
            row.witness_counts for row in region if r14.raw_bound(row) == record["prior_bound"]
        )
        assert r14.r8.validate_support_assignment(maximizing, support)
        assert r14.r8.witness_costs(maximizing, support) == (
            record["witness_residual_s2"],
            record["s4"]["feasible_upper_bound"],
        )


def test_exact_pair_tables_and_fractional_outside_dual_are_conservative(
    result: dict[str, Any],
) -> None:
    table_api = "_pair_event_correction_table"
    for state in cast(list[dict[str, Any]], result["STATE_OWNER_CERTIFICATES"]):
        for row in cast(list[dict[str, Any]], state["region_moment_certificates"]):
            certificate = cast(dict[str, Any], row["certificate"])
            slope = Fraction(*certificate["outside_slope"])
            for pair in cast(list[dict[str, Any]], certificate["pair_table_rows"]):
                table = getattr(r14.r8, table_api)(*pair["types"])
                assert pair["exact_four_event_table_sha256"] == r14.digest(table)
                assert all(cost[4] >= pair["pair_minimum"] + slope * cost[3] for cost in table)
                assert all(cost[5] >= pair["s4_minimum"] for cost in table)


def test_feasible_s4_attempts_are_not_promoted_to_minimum_certificates(
    result: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def feasible(_: r14.CountVector, kind: str) -> dict[str, Any]:
        return {
            "kind": kind,
            "status": "FEASIBLE",
            "incumbent_s4": 38_213,
            "observed_best_objective_bound_not_a_proof": 1_000_000_000,
            "certified_minimum": None,
            "support": None,
        }

    monkeypatch.setattr(r14, "run_s4_attempt", feasible)
    chase = r14.Chase(
        states=r14.initial_state_terms(),
        baseline=365_048_628,
        next_loss=r14.START_LOSS,
        classified_maximum=("prior", 356_534_853),
    )
    record = r14.certify_state(chase, r14.START_STATE_ID)
    assert record["s4"]["certified_lower_bound"] == 2_016
    assert not record["s4"]["minimum_proven"]
    assert record["new_bound"] == result["STATE_OWNER_CERTIFICATES"][0]["new_bound"]
    for state in cast(list[dict[str, Any]], result["STATE_OWNER_CERTIFICATES"]):
        for attempt in cast(list[dict[str, Any]], state["s4"]["attempts"]):
            if attempt["status"] != "OPTIMAL":
                assert attempt["certified_minimum"] is None


def test_attained_tail_conservation_no_skipped_levels_and_exact_first_stop(
    result: dict[str, Any],
) -> None:
    levels = r14.tail_census(int(result["NEXT_UNCLASSIFIED_LOSS"]))
    records = cast(list[dict[str, Any]], result["TAIL_LEVEL_CERTIFICATES"])
    assert len(levels) == len(records) + 1
    assert levels[0][0] == r14.START_LOSS
    assert levels[-1][0] == result["NEXT_UNCLASSIFIED_LOSS"]
    for index, record in enumerate(records):
        loss, counts = levels[index]
        assert record["local_loss"] == loss
        assert record["next_unclassified_loss"] == levels[index + 1][0]
        assert record["vector_count"] == len(counts)
        assert record["counts_sha256"] == r14.digest(counts)
        assert record["realizable_count"] + record["unrealizable_count"] == len(counts)
        assert record["unresolved_count"] == 0
        assert 365_048_628 - loss > record["active_state_threshold"]
    trajectory = cast(list[dict[str, Any]], result["OWNER_ACTION_TRAJECTORY"])
    assert all(
        event["r3_bound"] > r14.START_R3_BOUND - r14.DROP_TARGET for event in trajectory[:-1]
    )
    assert trajectory[-1]["r3_bound"] <= r14.START_R3_BOUND - r14.DROP_TARGET
    assert result["TAIL_LEVELS_PROCESSED"] == 398
    assert result["STATE_OWNERS_PROCESSED"] == 2
    assert result["OWNER_TRANSITION_COUNT"] == 3
    assert result["STOP_CONDITION"] == r14.STOP_B
    assert result["FINAL_OWNER_ID"] == r14.TAIL_ID
    assert result["R3_BOUND"] == 356_698_986
    assert result["R3_DROP"] == 100_224
    assert result["R3_BOUND"] == max(
        result["STATE_MAX_BOUND"],
        result["UNCLASSIFIED_TAIL_BOUND"],
        result["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"],
    )
    assert result["REMAINING_GAP"] == result["R3_BOUND"] - r14.INCUMBENT
    assert result["NON_OWNER_STATE_TERMS_CHANGED"] == 0
    final = {row["stable_id"]: row["bound"] for row in result["CURRENT_STATE_TERMS"]}
    processed = set(result["PROCESSED_STATE_OWNER_IDS"])
    assert len(processed) == 2
    assert all(
        final[identifier] == bound
        for identifier, bound in r14.initial_state_terms()
        if identifier not in processed
    )


def test_solver_free_replay_matches_authoritative_owner_switches(
    result: dict[str, Any],
) -> None:
    replay = r14.build_result(use_solvers=False)
    for key in (
        "R3_BOUND",
        "R3_DROP",
        "CURRENT_STATE_TERMS",
        "OWNER_TRANSITIONS",
        "OWNER_ACTION_TRAJECTORY",
        "TAIL_LEVEL_CERTIFICATES",
        "FINAL_OWNER_ID",
        "NEXT_UNCLASSIFIED_LOSS",
        "STATE_OWNERS_PROCESSED",
        "TAIL_LEVELS_PROCESSED",
    ):
        assert replay[key] == result[key]
