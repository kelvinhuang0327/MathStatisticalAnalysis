"""Focused plateau, witness, and effective-tail checks for R12."""

from __future__ import annotations

import json

from lottolab.research import b649_k20_r3_anchor_incidence_bound_r5 as r5
from lottolab.research import b649_k20_r3_exact_anchor_neighborhood_envelope_r6 as r6
from lottolab.research import b649_k20_r3_frontier_realizability_bound_r8 as r8
from lottolab.research.b649_k20_r3_corrected_tail_min_loss_plateau_r12 import (
    ELIMINATED,
    OUTSIDE_TICKET_COUNT,
    PRIOR_MINIMUM_OMITTED_LOSS,
    PRIOR_R3_BOUND,
    RESULT_PATH,
    WITNESS_REALIZED,
    build_result,
    canonical_primitives,
    canonical_uncorrected_baseline,
    classify_tail_plateaus,
    classify_vector,
    construct_support_witness,
    local_loss,
    non_owner_state_terms,
    tail_level_census,
    verify_upstream_fingerprints,
)

CUTOFF = 6_695_798
FIRST_ATTAINED_TAIL_LOSS = 6_696_172


def _impossible_vector() -> tuple[int, ...]:
    # Every (0, 3, 3, 0) ticket holds all six A/B-exclusive labels: pair overlap 6.
    counts = [0] * len(r5.anchor_incidence_profiles())
    counts[15] = OUTSIDE_TICKET_COUNT
    return tuple(counts)


def test_canonical_primitives_and_pinned_authority_pass() -> None:
    primitives = canonical_primitives()

    assert primitives["SINGLE_TICKET_ANY_PRIZE"] == 18_611_432
    assert primitives["PAIR_DIAGONAL_I6"] == 18_611_432
    assert primitives["K20_S1"] == 372_228_640
    assert len(verify_upstream_fingerprints()) == 2
    assert canonical_uncorrected_baseline() == 372_228_640 - 7_180_012


def test_start_plateau_is_empty_and_first_attained_level_is_exact() -> None:
    census = tail_level_census(33)
    losses = r6.local_losses(r5.anchor_incidence_profiles())
    below_first = [
        local_loss(vector, losses)
        for vector in r6.iter_type_count_vectors(
            losses, OUTSIDE_TICKET_COUNT, FIRST_ATTAINED_TAIL_LOSS - 1
        )
    ]

    assert census.vectors_at_or_below_cutoff == 10_816
    assert census.levels[0][0] == FIRST_ATTAINED_TAIL_LOSS
    assert PRIOR_MINIMUM_OMITTED_LOSS < FIRST_ATTAINED_TAIL_LOSS
    assert all(loss <= CUTOFF for loss in below_first)
    assert len(below_first) == 10_816
    levels = [loss for loss, _ in census.levels]
    assert levels == sorted(set(levels))
    assert all(
        local_loss(vector, losses) == loss for loss, vectors in census.levels for vector in vectors
    )


def test_support_witness_is_independently_valid_and_fails_closed() -> None:
    vector = tail_level_census(1).levels[0][1][0]
    witness = construct_support_witness(vector)

    assert witness is not None
    assert r8.validate_support_assignment(vector, witness)
    collided = (witness[1], *witness[1:])
    assert not r8.validate_support_assignment(vector, collided)

    impossible = _impossible_vector()
    assert not r6.aggregate_count_vector_is_feasible(impossible)
    assert construct_support_witness(impossible, restarts=2, ticket_tries=8) is None


def test_aggregate_infeasible_vector_is_eliminated_without_a_bound() -> None:
    row = classify_vector(_impossible_vector(), canonical_uncorrected_baseline())

    assert row.status == ELIMINATED
    assert row.vector_bound is None
    assert row.correction is None


def test_effective_tail_floor_is_the_first_unprocessed_attained_level() -> None:
    baseline = canonical_uncorrected_baseline()
    census = tail_level_census(4)
    for budget in (1, 3):
        certificate = classify_tail_plateaus(budget)

        assert len(certificate.levels) == budget
        assert certificate.stop_condition == "D_LOSS_LEVEL_BUDGET_EXHAUSTED"
        assert certificate.effective_tail_bound == baseline - census.levels[budget][0]
        assert all(
            row.vector_bound is not None and row.vector_bound < certificate.effective_tail_bound
            for level in certificate.levels
            for row in level.vectors
        )


def test_full_budget_certificate_tightens_only_the_corrected_tail() -> None:
    result = build_result()
    terms = result["TOP_LEVEL_R3_TERMS"]
    state_terms = [(term["stable_id"], term["bound"]) for term in terms[1:]]

    assert result["LOSS_LEVELS_PROCESSED"] == 32
    assert result["STOP_CONDITION"] == "D_LOSS_LEVEL_BUDGET_EXHAUSTED"
    assert result["START_PLATEAU"]["CERTIFIED_EMPTY_LOSS_INTERVAL"] == [
        PRIOR_MINIMUM_OMITTED_LOSS,
        FIRST_ATTAINED_TAIL_LOSS - 1,
    ]
    assert result["MIN_REALIZABLE_TAIL_LOSS"] == FIRST_ATTAINED_TAIL_LOSS
    assert result["TAIL_VECTOR_COUNT"] == 235
    assert result["UNREALIZABLE_VECTOR_COUNT"] == 0
    assert result["REALIZABLE_VECTOR_COUNT"] == 235
    assert result["UNRESOLVED_VECTOR_COUNT"] == 0
    assert result["EFFECTIVE_TAIL_CERTIFICATE"]["TYPE_COUNT_LOSS"] == 6_711_565
    assert result["CORRECTED_TAIL_BOUND"] == 358_337_063
    assert result["R3_BOUND"] == 358_337_063 < PRIOR_R3_BOUND
    assert result["R3_TIGHTENING"] == 15_764
    assert result["CURRENT_BOUND_OWNER_SET"] == ["corrected-tail"]
    assert result["TOP_STATE_BOUND"] == 356_799_210
    assert tuple(state_terms) == non_owner_state_terms()
    assert (result["SUCCESS_A"], result["SUCCESS_B"], result["SUCCESS_C"]) == (
        False,
        False,
        True,
    )
    assert all(
        level["witness_realized"] == level["vector_count"] for level in result["LOSS_LEVEL_ROWS"]
    )


def test_written_certificate_matches_a_fresh_rebuild() -> None:
    stored = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    rebuilt = build_result()
    stored.pop("PROOF_WALL_SECONDS")
    rebuilt.pop("PROOF_WALL_SECONDS")

    assert stored == rebuilt
    assert classify_tail_plateaus().levels[-1].vectors[0].status == WITNESS_REALIZED


def test_every_processed_realized_vector_has_an_independently_valid_witness() -> None:
    rows = [row for level in classify_tail_plateaus().levels for row in level.vectors]

    assert len(rows) == 235
    assert all(
        row.status == WITNESS_REALIZED
        and row.witness is not None
        and r8.validate_support_assignment(row.counts, row.witness)
        for row in rows
    )
