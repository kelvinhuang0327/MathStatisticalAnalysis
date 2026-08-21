"""Donor parity and failure-closure tests for unpopularity selection."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from lottolab.domain.unpopularity_candidate_selection import (
    BASE_SCORE,
    BIG_LOTTO_CANDIDATE_BOUNDS,
    BIRTHDAY_COUNT_SQUARED_PENALTY,
    BIRTHDAY_NUMBER_MAX,
    CONSECUTIVE_PAIR_PENALTY,
    DONOR_SOURCE,
    DONOR_SOURCE_SHA256,
    HIGH_NUMBER_REWARD,
    Candidate,
    CandidateBounds,
    InvalidCandidate,
    InvalidObjectiveScore,
    select_highest_scored_candidate,
    select_unpopularity_candidate,
    unpopularity_score,
)


def test_donor_identity_and_constants_are_frozen() -> None:
    assert DONOR_SOURCE == "lottery_api/models/prize_optimizer.py"
    assert DONOR_SOURCE_SHA256 == (
        "f3547f9b190baa031dbeff9703509a3bc262bda7426a0fd13d89e1654f99771b"
    )
    assert (
        BASE_SCORE,
        BIRTHDAY_NUMBER_MAX,
        BIRTHDAY_COUNT_SQUARED_PENALTY,
        HIGH_NUMBER_REWARD,
        CONSECUTIVE_PAIR_PENALTY,
    ) == (100.0, 31, 5.0, 15.0, 20.0)
    assert CandidateBounds(1, 49, 6) == BIG_LOTTO_CANDIDATE_BOUNDS


@pytest.mark.parametrize(
    ("candidate", "expected"),
    (
        ((32, 34, 36, 38, 40, 42), 190.0),
        ((1, 3, 5, 7, 9, 11), -80.0),
        ((32, 33, 34, 35, 36, 37), 90.0),
        ((1, 2, 32, 33, 40, 49), 100.0),
    ),
)
def test_score_matches_donor_golden_cases(
    candidate: Candidate,
    expected: float,
) -> None:
    assert unpopularity_score(candidate) == expected


def test_selection_preserves_first_max_tie_and_candidate_order() -> None:
    first = (42, 32, 34, 36, 38, 40)
    tied_later = (33, 35, 37, 39, 41, 43)
    lower = (1, 2, 3, 4, 5, 6)

    selected = select_unpopularity_candidate((lower, first, tied_later))

    assert selected == first
    assert unpopularity_score(first) == unpopularity_score(tied_later) == 190.0


def test_selection_invariant_returns_an_input_maximizer_without_mutation() -> None:
    candidates = [
        [1, 3, 5, 7, 9, 11],
        [1, 2, 32, 33, 40, 49],
        [32, 34, 36, 38, 40, 42],
    ]
    before = [candidate.copy() for candidate in candidates]

    selected = select_unpopularity_candidate(candidates)

    assert selected in tuple(tuple(candidate) for candidate in candidates)
    assert selected is not None
    assert unpopularity_score(selected) == max(
        unpopularity_score(candidate) for candidate in candidates
    )
    assert candidates == before


def test_injected_objective_executes_once_per_candidate_in_source_order() -> None:
    candidates = (
        (1, 3, 5, 7, 9, 11),
        (2, 4, 6, 8, 10, 12),
        (32, 34, 36, 38, 40, 42),
    )
    observed: list[Candidate] = []

    def objective(candidate: Candidate) -> float:
        observed.append(candidate)
        return float(candidate[0])

    assert (
        select_highest_scored_candidate(
            candidates,
            objective=objective,
        )
        == candidates[-1]
    )
    assert observed == list(candidates)


def test_fixed_input_is_byte_stable_across_repeated_execution() -> None:
    candidates = (
        (1, 3, 5, 7, 9, 11),
        (1, 2, 32, 33, 40, 49),
        (32, 34, 36, 38, 40, 42),
    )

    first = select_unpopularity_candidate(candidates)
    assert first == (32, 34, 36, 38, 40, 42)
    assert all(select_unpopularity_candidate(candidates) == first for _ in range(20))


@pytest.mark.parametrize(
    "candidate",
    (
        (1, 2, 3, 4, 5),
        (1, 2, 3, 4, 5, 5),
        (0, 2, 3, 4, 5, 6),
        (1, 2, 3, 4, 5, 50),
        (True, 2, 3, 4, 5, 6),
        (1, 2, 3, 4, 5, 6.0),
        "123456",
    ),
)
def test_invalid_candidates_fail_closed(candidate: object) -> None:
    with pytest.raises(InvalidCandidate):
        unpopularity_score(candidate)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "constructor",
    (
        lambda: CandidateBounds(True, 49, 6),
        lambda: CandidateBounds(1, 49, 0),
        lambda: CandidateBounds(49, 1, 6),
        lambda: CandidateBounds(1, 3, 4),
    ),
)
def test_invalid_bounds_fail_closed(constructor: Callable[[], CandidateBounds]) -> None:
    with pytest.raises((TypeError, ValueError)):
        constructor()


def test_empty_candidate_space_preserves_closed_donor_semantics() -> None:
    def should_not_run(candidate: Candidate) -> float:
        raise AssertionError(f"objective unexpectedly called for {candidate}")

    assert select_unpopularity_candidate(()) is None
    assert select_highest_scored_candidate((), objective=should_not_run) is None


@pytest.mark.parametrize("score", (float("nan"), float("inf"), float("-inf"), True))
def test_non_finite_or_boolean_objective_scores_fail_closed(score: object) -> None:
    def invalid_objective(candidate: Candidate) -> float:
        del candidate
        return score  # type: ignore[return-value]

    with pytest.raises(InvalidObjectiveScore):
        select_highest_scored_candidate(
            ((1, 2, 3, 4, 5, 6),),
            objective=invalid_objective,
        )


def test_objective_failure_is_not_silently_degraded() -> None:
    def failing_objective(candidate: Candidate) -> float:
        raise RuntimeError(f"cannot score {candidate}")

    with pytest.raises(RuntimeError, match="cannot score"):
        select_highest_scored_candidate(
            ((1, 2, 3, 4, 5, 6),),
            objective=failing_objective,
        )
