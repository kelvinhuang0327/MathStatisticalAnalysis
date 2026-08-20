"""Deterministic, bounded candidate selection from the legacy prize optimizer.

The donor is ``lottery_api/models/prize_optimizer.py`` in the preserved
``LotteryNewMeraged`` source snapshot (sha256
``f3547f9b190baa031dbeff9703509a3bc262bda7426a0fd13d89e1654f99771b``).
That snapshot has no Git metadata, so this module does not claim a donor
commit identity.

For valid candidates, :func:`unpopularity_score` preserves the donor's exact
combination-level objective and :func:`select_unpopularity_candidate`
preserves its first-maximum tie behavior.  Target-owned validation closes
malformed or out-of-bounds input before the objective runs.  The generic
selection step accepts an injected objective so it remains independent of
strategy catalogs, persistence, schedulers, networks, and process runtime.

This is a popularity heuristic for candidate selection, not a predictive-
performance or prize-value claim.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from numbers import Real

DONOR_SOURCE = "lottery_api/models/prize_optimizer.py"
DONOR_SOURCE_SHA256 = "f3547f9b190baa031dbeff9703509a3bc262bda7426a0fd13d89e1654f99771b"

BASE_SCORE = 100.0
BIRTHDAY_NUMBER_MAX = 31
BIRTHDAY_COUNT_SQUARED_PENALTY = 5.0
HIGH_NUMBER_REWARD = 15.0
CONSECUTIVE_PAIR_PENALTY = 20.0

Candidate = tuple[int, ...]
CandidateObjective = Callable[[Candidate], float]


class CandidateSelectionError(ValueError):
    """Base class for closed candidate-selection failures."""


class InvalidCandidate(CandidateSelectionError):
    """Raised when a candidate does not satisfy its declared bounds."""


class InvalidObjectiveScore(CandidateSelectionError):
    """Raised when an injected objective does not return a finite real score."""


@dataclass(frozen=True, slots=True)
class CandidateBounds:
    """Closed integer bounds for one fixed-width candidate."""

    min_number: int
    max_number: int
    pick_count: int

    def __post_init__(self) -> None:
        for field_name, value in (
            ("min_number", self.min_number),
            ("max_number", self.max_number),
            ("pick_count", self.pick_count),
        ):
            if type(value) is not int:
                raise TypeError(f"{field_name} must be an integer")
        if self.min_number > self.max_number:
            raise ValueError("min_number must not exceed max_number")
        if self.pick_count <= 0:
            raise ValueError("pick_count must be positive")
        if self.pick_count > self.max_number - self.min_number + 1:
            raise ValueError("pick_count exceeds the bounded number space")


BIG_LOTTO_CANDIDATE_BOUNDS = CandidateBounds(
    min_number=1,
    max_number=49,
    pick_count=6,
)


def _validate_candidate(
    numbers: Sequence[int],
    *,
    bounds: CandidateBounds,
) -> Candidate:
    if isinstance(numbers, (str, bytes, bytearray)):
        raise InvalidCandidate("candidate must be a sequence of integers")

    candidate = tuple(numbers)
    if len(candidate) != bounds.pick_count:
        raise InvalidCandidate(f"candidate must contain exactly {bounds.pick_count} numbers")
    if any(type(number) is not int for number in candidate):
        raise InvalidCandidate("candidate numbers must be integers")
    if len(set(candidate)) != bounds.pick_count:
        raise InvalidCandidate("candidate numbers must be unique")
    if any(number < bounds.min_number or number > bounds.max_number for number in candidate):
        raise InvalidCandidate(
            f"candidate number is outside [{bounds.min_number}, {bounds.max_number}]"
        )
    return candidate


def _unpopularity_score_validated(candidate: Candidate) -> float:
    score = BASE_SCORE
    birthday_count = sum(number <= BIRTHDAY_NUMBER_MAX for number in candidate)
    score -= birthday_count**2 * BIRTHDAY_COUNT_SQUARED_PENALTY

    high_number_count = sum(number > BIRTHDAY_NUMBER_MAX for number in candidate)
    score += high_number_count * HIGH_NUMBER_REWARD

    ordered = sorted(candidate)
    score -= (
        sum(ordered[index + 1] - ordered[index] == 1 for index in range(len(ordered) - 1))
        * CONSECUTIVE_PAIR_PENALTY
    )
    return score


def unpopularity_score(
    numbers: Sequence[int],
    *,
    bounds: CandidateBounds = BIG_LOTTO_CANDIDATE_BOUNDS,
) -> float:
    """Return the donor-exact score for one valid bounded candidate."""

    return _unpopularity_score_validated(_validate_candidate(numbers, bounds=bounds))


def select_highest_scored_candidate(
    candidates: Sequence[Sequence[int]],
    *,
    objective: CandidateObjective,
    bounds: CandidateBounds = BIG_LOTTO_CANDIDATE_BOUNDS,
) -> Candidate | None:
    """Return the first finite-score maximizer, or ``None`` for no candidates.

    Each candidate is normalized to an immutable tuple without reordering.
    The objective executes exactly once per valid candidate in source order.
    Malformed candidates and non-finite objective values fail closed.
    Exceptions raised by the objective propagate to the caller.
    """

    if not callable(objective):
        raise TypeError("objective must be callable")
    if isinstance(candidates, (str, bytes, bytearray)):
        raise InvalidCandidate("candidates must be a sequence of candidates")

    normalized = tuple(_validate_candidate(candidate, bounds=bounds) for candidate in candidates)
    if not normalized:
        return None

    best_candidate: Candidate | None = None
    best_score: float | None = None
    for candidate in normalized:
        raw_score = objective(candidate)
        if isinstance(raw_score, bool) or not isinstance(raw_score, Real):
            raise InvalidObjectiveScore("objective score must be a finite real number")
        score = float(raw_score)
        if not math.isfinite(score):
            raise InvalidObjectiveScore("objective score must be a finite real number")
        if best_score is None or score > best_score:
            best_candidate = candidate
            best_score = score

    return best_candidate


def select_unpopularity_candidate(
    candidates: Sequence[Sequence[int]],
    *,
    bounds: CandidateBounds = BIG_LOTTO_CANDIDATE_BOUNDS,
) -> Candidate | None:
    """Select the donor's first highest-unpopularity candidate."""

    return select_highest_scored_candidate(
        candidates,
        objective=_unpopularity_score_validated,
        bounds=bounds,
    )


__all__ = [
    "BASE_SCORE",
    "BIG_LOTTO_CANDIDATE_BOUNDS",
    "BIRTHDAY_COUNT_SQUARED_PENALTY",
    "BIRTHDAY_NUMBER_MAX",
    "CONSECUTIVE_PAIR_PENALTY",
    "DONOR_SOURCE",
    "DONOR_SOURCE_SHA256",
    "HIGH_NUMBER_REWARD",
    "Candidate",
    "CandidateBounds",
    "CandidateObjective",
    "CandidateSelectionError",
    "InvalidCandidate",
    "InvalidObjectiveScore",
    "select_highest_scored_candidate",
    "select_unpopularity_candidate",
    "unpopularity_score",
]
