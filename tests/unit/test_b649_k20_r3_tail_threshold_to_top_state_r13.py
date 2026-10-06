"""Focused crossover, no-rerun, witness, correction, and owner-switch checks for R13."""

from __future__ import annotations

import json
from itertools import pairwise

import pytest

from lottolab.research import b649_k20_r3_anchor_incidence_bound_r5 as r5
from lottolab.research import b649_k20_r3_corrected_tail_min_loss_plateau_r12 as r12
from lottolab.research import b649_k20_r3_exact_anchor_neighborhood_envelope_r6 as r6
from lottolab.research import b649_k20_r3_frontier_realizability_bound_r8 as r8
from lottolab.research.b649_k20_r3_tail_threshold_to_top_state_r13 import (
    CENSUS_LIMIT_REACHED,
    CROSSOVER_LOSS_THRESHOLD,
    FOUR_TICKET_APPLIED,
    FOUR_TICKET_NOT_APPLICABLE,
    FOUR_TICKET_NOT_REQUIRED,
    RESULT_PATH,
    START_UNCLASSIFIED_LOSS,
    STOP_B,
    STOP_C,
    STOP_D,
    TOP_STATE_BOUND,
    UNCLASSIFIED_TAIL_TERM,
    ClassifiedVector,
    build_result,
    canonical_primitives,
    classify_to_crossover,
    classify_vector,
    crossover_loss_threshold,
    four_ticket_penalty,
    r12_carried_maximum,
    state_terms,
    verify_upstream_fingerprints,
    walk_attained_levels,
)

TOP_STATE_ID = "state:s2-12695020-s3-735532"
R12_WORST_VECTOR_ID = "tail-vector:L6709346:0x6,1x11,17x1"


def _dense(sparse: list[tuple[int, int]]) -> tuple[int, ...]:
    counts = [0] * len(r5.anchor_incidence_profiles())
    for index, count in sparse:
        counts[index] = count
    return tuple(counts)


def _synthetic_row(counts: tuple[int, ...], loss: int, bound: int) -> ClassifiedVector:
    correction = 1_000 - loss - bound
    return ClassifiedVector(
        vector_id=f"tail-vector:L{loss}",
        counts=counts,
        local_loss=loss,
        status=r12.WITNESS_REALIZED,
        pair_union_penalty=correction,
        forest_floor=0,
        r6_correction=correction,
        four_ticket_status=FOUR_TICKET_NOT_REQUIRED,
        four_ticket_penalty=None,
        correction=correction,
        vector_bound=bound,
        witness=None,
    )


def test_canonical_primitives_and_exact_crossover_arithmetic() -> None:
    primitives = canonical_primitives()
    baseline = r12.canonical_uncorrected_baseline()

    assert primitives["SINGLE_TICKET_ANY_PRIZE"] == 18_611_432
    assert primitives["PAIR_DIAGONAL_I6"] == 18_611_432
    assert primitives["K20_S1"] == 372_228_640
    assert len(verify_upstream_fingerprints()) == 2
    assert 372_228_640 - 7_180_012 - 356_799_210 == 8_249_418
    assert crossover_loss_threshold() == CROSSOVER_LOSS_THRESHOLD == 8_249_418
    assert baseline == 372_228_640 - 7_180_012
    assert baseline - CROSSOVER_LOSS_THRESHOLD == TOP_STATE_BOUND
    assert baseline - (CROSSOVER_LOSS_THRESHOLD - 1) > TOP_STATE_BOUND


def test_r12_vectors_are_fingerprint_validated_and_never_reclassified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    census, walk, _ = classify_to_crossover()
    prior_vectors = {vector for _, vectors in census.prior_levels for vector in vectors}

    assert len(census.prior_levels) == 32
    assert len(prior_vectors) == 235
    assert census.prior_levels[0][0] == 6_696_172
    assert census.levels[0][0] == START_UNCLASSIFIED_LOSS
    assert not prior_vectors & {row.counts for row in walk.rows}
    assert min(row.local_loss for row in walk.rows) == START_UNCLASSIFIED_LOSS
    assert r12_carried_maximum() == (R12_WORST_VECTOR_ID, 356_534_853)

    def forbidden(*_: object) -> None:
        raise RuntimeError("R12 machinery was invoked for an R12-certified vector")

    monkeypatch.setattr(r12, "classify_vector", forbidden)
    with pytest.raises(AssertionError, match="must not reclassify"):
        classify_vector(sorted(prior_vectors)[0], r12.canonical_uncorrected_baseline())


def test_attained_loss_ordering_invariant_matches_an_independent_census() -> None:
    _, walk, _ = classify_to_crossover()
    steps = walk.steps
    final = steps[-1]
    losses = r6.local_losses(r5.anchor_incidence_profiles())
    independent: dict[int, int] = {}
    for vector in r6.iter_type_count_vectors(
        losses, r12.OUTSIDE_TICKET_COUNT, final.next_unclassified_loss
    ):
        loss = r12.local_loss(vector, losses)
        if loss >= START_UNCLASSIFIED_LOSS:
            independent[loss] = independent.get(loss, 0) + 1

    attained = sorted(independent)
    assert attained[:-1] == [step.local_loss for step in steps]
    assert attained[-1] == final.next_unclassified_loss
    assert [independent[step.local_loss] for step in steps] == [step.vector_count for step in steps]
    assert steps[0].local_loss == START_UNCLASSIFIED_LOSS
    assert all(left.local_loss < right.local_loss for left, right in pairwise(steps))
    assert all(left.next_unclassified_loss == right.local_loss for left, right in pairwise(steps))
    assert all(left.r3_bound >= right.r3_bound for left, right in pairwise(steps))
    assert all(
        left.unclassified_tail_bound > right.unclassified_tail_bound
        for left, right in pairwise(steps)
    )
    assert [row.local_loss for row in walk.rows] == sorted(row.local_loss for row in walk.rows)
    assert steps[-2].next_unclassified_loss < CROSSOVER_LOSS_THRESHOLD
    assert final.local_loss < CROSSOVER_LOSS_THRESHOLD <= final.next_unclassified_loss


def test_every_new_vector_has_an_independently_valid_witness() -> None:
    rows = classify_to_crossover()[1].rows

    assert len(rows) == 34_767
    assert all(
        row.status == r12.WITNESS_REALIZED
        and row.witness is not None
        and r8.validate_support_assignment(row.counts, row.witness)
        for row in rows
    )
    witness = rows[0].witness
    assert witness is not None
    assert not r8.validate_support_assignment(rows[0].counts, (witness[1], *witness[1:]))


def test_classified_vector_corrections_and_load_bearing_four_ticket_floor() -> None:
    baseline = r12.canonical_uncorrected_baseline()
    rows = classify_to_crossover()[1].rows
    for row in rows:
        assert row.pair_union_penalty is not None and row.forest_floor is not None
        assert row.correction is not None and row.vector_bound is not None
        assert row.correction == row.r6_correction == max(row.pair_union_penalty, row.forest_floor)
        assert row.vector_bound == baseline - row.local_loss - row.correction
        assert row.vector_bound <= TOP_STATE_BOUND
        assert row.four_ticket_status == FOUR_TICKET_NOT_REQUIRED
    forest_row = next(
        row for row in rows if (row.forest_floor or 0) > (row.pair_union_penalty or 0)
    )
    assert forest_row.correction == forest_row.forest_floor

    vector = _dense([(0, 6), (4, 11), (9, 1)])
    default = classify_vector(vector, baseline)
    assert default.local_loss == 6_742_484
    assert default.correction == default.pair_union_penalty == 1_804_199
    assert default.vector_bound == 356_501_945 <= TOP_STATE_BOUND

    forced = classify_vector(vector, baseline, 356_000_000)
    assert forced.four_ticket_status == FOUR_TICKET_APPLIED
    assert forced.four_ticket_penalty == four_ticket_penalty(vector) == 4_989_485
    assert forced.correction == 4_989_485
    assert forced.vector_bound == baseline - 6_742_484 - 4_989_485 == 353_316_659


def test_four_ticket_floor_fails_closed_without_an_outside_overlap_pattern() -> None:
    census = classify_to_crossover()[0]
    vector = next(vector for _, vectors in census.levels for vector in vectors if vector[15])

    assert r5.anchor_incidence_profiles()[15].outside == 0
    assert four_ticket_penalty(vector) is None
    with pytest.raises(AssertionError, match="no outside overlap pattern"):
        r8.state_moment_floor(vector)
    row = classify_vector(vector, r12.canonical_uncorrected_baseline(), 0)
    assert row.four_ticket_status == FOUR_TICKET_NOT_APPLICABLE
    assert row.correction == row.r6_correction


def test_owner_switches_to_a_classified_vector_and_stops_classifying() -> None:
    bounds: dict[tuple[int, ...], tuple[int, int]] = {
        (1,): (40, 930),
        (2,): (60, 910),
        (3,): (120, 870),
        (4,): (300, 600),
    }
    calls: list[tuple[int, ...]] = []

    def classify(counts: tuple[int, ...]) -> ClassifiedVector:
        calls.append(counts)
        return _synthetic_row(counts, *bounds[counts])

    walk = walk_attained_levels(
        [(loss, (counts,)) for counts, (loss, _) in bounds.items()],
        classify,
        baseline=1_000,
        states=(("state:top", 900), ("state:low", 850)),
        carried_maximum=("tail-vector:carried", 880),
        r4_reference=500,
    )

    assert walk.stop_condition == STOP_C
    assert calls == [(1,), (2,)]
    assert [step.owner_set for step in walk.steps] == [
        (UNCLASSIFIED_TAIL_TERM,),
        ("tail-vector:L40",),
    ]
    final = walk.steps[-1]
    assert final.unclassified_tail_bound == 880 < 900 < final.r3_bound == 930
    assert final.max_classified_vector_id == "tail-vector:L40"


def test_tail_hands_ownership_to_the_top_state_at_the_crossover() -> None:
    bounds: dict[tuple[int, ...], tuple[int, int]] = {
        (1,): (50, 860),
        (2,): (80, 870),
        (3,): (120, 860),
        (4,): (200, 700),
    }
    calls: list[tuple[int, ...]] = []

    def classify(counts: tuple[int, ...]) -> ClassifiedVector:
        calls.append(counts)
        return _synthetic_row(counts, *bounds[counts])

    levels = [(loss, (counts,)) for counts, (loss, _) in bounds.items()]
    states = (("state:top", 900), ("state:low", 850))
    walk = walk_attained_levels(
        levels,
        classify,
        baseline=1_000,
        states=states,
        carried_maximum=("tail-vector:carried", 880),
        r4_reference=500,
    )

    assert walk.stop_condition == STOP_B
    assert calls == [(1,), (2,)]
    assert [step.r3_bound for step in walk.steps] == [920, 900]
    assert walk.steps[-1].owner_set == ("state:top",)
    assert walk.steps[-1].max_classified_vector_id == "tail-vector:carried"

    short = walk_attained_levels(
        levels[:1], classify, baseline=1_000, states=states, carried_maximum=("c", 0)
    )
    assert (short.stop_condition, short.steps) == (CENSUS_LIMIT_REACHED, ())
    timed_out = walk_attained_levels(
        levels,
        classify,
        baseline=1_000,
        states=states,
        carried_maximum=("c", 0),
        wall_budget_seconds=0.0,
    )
    assert (timed_out.stop_condition, timed_out.steps) == (STOP_D, ())


def test_full_certificate_reaches_success_b_at_the_crossover() -> None:
    result = build_result()
    terms = result["TOP_LEVEL_R3_TERMS"]

    assert result["TASK_STATUS"] == "SUCCESS_B_R3_AT_OR_BELOW_TOP_STATE"
    assert result["STOP_CONDITION"] == STOP_B
    assert result["CANONICAL_PRIMITIVE_STATUS"] == "PASS"
    assert result["START_UNCLASSIFIED_LOSS"] == 6_711_565
    assert result["CROSSOVER_LOSS_THRESHOLD"] == 8_249_418
    assert result["NEW_LOSS_LEVEL_COUNT"] == 3_621
    assert result["NEW_VECTOR_COUNT"] == 34_767
    assert result["TOTAL_CLASSIFIED_VECTOR_COUNT"] == 35_002
    assert result["REALIZABLE_VECTOR_COUNT"] == 35_002
    assert result["UNREALIZABLE_VECTOR_COUNT"] == 0
    assert result["UNRESOLVED_VECTOR_COUNT"] == 0
    assert result["NEXT_UNCLASSIFIED_LOSS"] == 8_249_444
    assert result["UNCLASSIFIED_TAIL_BOUND"] == 356_799_184
    assert result["MAX_CLASSIFIED_VECTOR_BOUND"] == 356_534_853
    assert result["MAX_CLASSIFIED_VECTOR_ID"] == R12_WORST_VECTOR_ID
    assert result["R3_BOUND"] == TOP_STATE_BOUND == 356_799_210
    assert result["R3_BOUND_OWNER"] == TOP_STATE_ID
    assert result["CURRENT_BOUND_OWNER_SET"] == [TOP_STATE_ID]
    assert result["R3_TIGHTENING"] == 1_537_853
    assert result["REMAINING_GAP"] == 43_559_549
    assert result["CLASSIFIED_VECTOR_CORRECTIONS"]["FOUR_TICKET_APPLIED_COUNT"] == 0
    assert result["NO_RERUN_GUARD"]["R12_LEVEL_SEQUENCE_MATCHES_CERTIFICATE"] is True
    assert [(term["stable_id"], term["bound"]) for term in terms[2:]] == list(state_terms())
    assert (result["SUCCESS_A"], result["SUCCESS_B"], result["SUCCESS_C"]) == (
        False,
        True,
        True,
    )
    assert [row["to"] for row in result["OWNER_TRANSITIONS"]] == [
        [UNCLASSIFIED_TAIL_TERM],
        [TOP_STATE_ID],
    ]


def test_written_certificate_matches_a_fresh_rebuild() -> None:
    stored = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    rebuilt = build_result()
    stored.pop("PROOF_WALL_SECONDS")
    rebuilt.pop("PROOF_WALL_SECONDS")

    assert stored == rebuilt
