"""Research-only Bayesian shrinkage plus time-decay candidate for BIG_LOTTO.

The posterior probability for each main number is a discounted Bernoulli
Beta-Binomial estimate. Its Beta prior is centered on that number's smoothed
rate in draws older than the selected window (or the rule-based 6/49 rate when
no older draws exist). Recent observations contribute fractional likelihood
weight exp(-ln(2) * age / half_life).

This module is deliberately pure: it reads no database, uses no randomness,
does not mutate histories, and has no catalog or production integration.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import exp, isfinite, log
from typing import Final

NUMBER_MIN: Final = 1
NUMBER_MAX: Final = 49
PICK_COUNT: Final = 6
BASE_RATE: Final = PICK_COUNT / NUMBER_MAX
BETA_PRIOR_STRENGTH: Final = 20.0
PORTFOLIO_OVERLAP_PENALTY: Final = BASE_RATE / 2.0
SUPPORTED_WINDOWS: Final = (50, 300, 750, 1500)
SUPPORTED_TICKET_COUNTS: Final = (1, 2, 3, 5)
DECAY_HALF_LIFE_MULTIPLIERS: Final = (0.5, 1.0, 2.0)
MIN_HALF_LIFE: Final = 25.0
MAX_HALF_LIFE: Final = 3000.0

type NumberDraw = Sequence[int]
type DrawHistory = Sequence[NumberDraw]
type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]


class BayesRecencyCandidateError(ValueError):
    """Raised when research inputs violate the candidate's fixed contract."""


def _validate_history(history: DrawHistory) -> tuple[Ticket, ...]:
    if isinstance(history, (str, bytes)):
        raise BayesRecencyCandidateError("history must be a sequence of draw rows")

    validated: list[Ticket] = []
    for row_index, row in enumerate(history):
        if isinstance(row, (str, bytes)) or not isinstance(row, Sequence):
            raise BayesRecencyCandidateError(f"history row {row_index} must be a sequence")
        numbers = tuple(row)
        if len(numbers) != PICK_COUNT:
            raise BayesRecencyCandidateError(
                f"history row {row_index} must contain exactly {PICK_COUNT} main numbers"
            )
        if any(type(number) is not int for number in numbers):
            raise BayesRecencyCandidateError(f"history row {row_index} must contain exact integers")
        if any(number < NUMBER_MIN or number > NUMBER_MAX for number in numbers):
            raise BayesRecencyCandidateError(f"history row {row_index} has a number outside 1..49")
        if len(set(numbers)) != PICK_COUNT:
            raise BayesRecencyCandidateError(
                f"history row {row_index} must contain six unique numbers"
            )
        validated.append(numbers)
    return tuple(validated)


def _validate_window(window_size: int) -> None:
    if type(window_size) is not int or window_size not in SUPPORTED_WINDOWS:
        raise BayesRecencyCandidateError(f"window_size must be one of {SUPPORTED_WINDOWS}")


def _validate_half_life(half_life: float) -> float:
    if isinstance(half_life, bool) or not isinstance(half_life, (int, float)):
        raise BayesRecencyCandidateError("half_life must be a finite number")
    resolved = float(half_life)
    if not isfinite(resolved) or not MIN_HALF_LIFE <= resolved <= MAX_HALF_LIFE:
        raise BayesRecencyCandidateError(
            f"half_life must be bounded to {MIN_HALF_LIFE:g}..{MAX_HALF_LIFE:g} draws"
        )
    return resolved


def bayes_shrunk_recency_scores(
    history: DrawHistory,
    *,
    window_size: int,
    half_life: float,
) -> tuple[float, ...]:
    """Return posterior inclusion means for numbers 1..49.

    History is oldest-first and must contain only draws before the target.
    The prior mean for each number is estimated from the history older than the
    selected window with a Jeffreys-smoothed rate. A fixed concentration of 20
    pseudo-draws shrinks the discounted recent evidence toward that estimate.
    """

    _validate_window(window_size)
    resolved_half_life = _validate_half_life(half_life)
    rows = _validate_history(history)

    recent = rows[-window_size:]
    older = rows[:-window_size] if len(rows) > window_size else ()

    older_counts = [0] * NUMBER_MAX
    for row in older:
        for number in row:
            older_counts[number - NUMBER_MIN] += 1

    if older:
        prior_means = tuple((count + 0.5) / (len(older) + 1.0) for count in older_counts)
    else:
        prior_means = (BASE_RATE,) * NUMBER_MAX

    weighted_successes = [0.0] * NUMBER_MAX
    weighted_trials = 0.0
    decay_rate = log(2.0) / resolved_half_life
    for age, row in enumerate(reversed(recent)):
        weight = exp(-decay_rate * age)
        weighted_trials += weight
        for number in row:
            weighted_successes[number - NUMBER_MIN] += weight

    denominator = BETA_PRIOR_STRENGTH + weighted_trials
    return tuple(
        (BETA_PRIOR_STRENGTH * prior_mean + success) / denominator
        for prior_mean, success in zip(prior_means, weighted_successes, strict=True)
    )


def _best_nonduplicate_ticket(
    adjusted_scores: tuple[float, ...],
    existing: set[Ticket],
) -> Ticket:
    ranked = sorted(
        range(NUMBER_MIN, NUMBER_MAX + 1),
        key=lambda number: (-adjusted_scores[number - NUMBER_MIN], number),
    )
    first_choice = tuple(sorted(ranked[:PICK_COUNT]))
    if first_choice not in existing:
        return first_choice

    first_set = set(first_choice)
    best_ticket: Ticket | None = None
    best_score = float("-inf")
    for outgoing in first_choice:
        for incoming in ranked[PICK_COUNT:]:
            candidate = tuple(sorted((first_set - {outgoing}) | {incoming}))
            if candidate in existing:
                continue
            score = sum(adjusted_scores[number - NUMBER_MIN] for number in candidate)
            if score > best_score or (
                score == best_score and (best_ticket is None or candidate < best_ticket)
            ):
                best_ticket = candidate
                best_score = score

    # K is capped at five, while one-swap alternatives alone number 258.
    if best_ticket is None:
        raise BayesRecencyCandidateError("could not construct a distinct legal ticket")
    return best_ticket


def portfolio_from_scores(
    scores: Sequence[float],
    *,
    ticket_count: int,
) -> Portfolio:
    """Build a deterministic, overlap-aware portfolio from 49 ranking scores.

    Each previously used number receives a fixed penalty equal to half the
    uniform inclusion rate (3/49). The penalty is not tuned against outcomes.
    Tickets are emitted in construction order and each ticket is ascending.
    """

    if type(ticket_count) is not int or ticket_count not in SUPPORTED_TICKET_COUNTS:
        raise BayesRecencyCandidateError(f"ticket_count must be one of {SUPPORTED_TICKET_COUNTS}")
    if isinstance(scores, (str, bytes)) or len(scores) != NUMBER_MAX:
        raise BayesRecencyCandidateError("scores must contain exactly 49 values")

    resolved_scores = tuple(float(value) for value in scores)
    if not all(isfinite(value) for value in resolved_scores):
        raise BayesRecencyCandidateError("scores must all be finite")

    usage_counts = [0] * NUMBER_MAX
    portfolio: list[Ticket] = []
    existing: set[Ticket] = set()
    for _ in range(ticket_count):
        adjusted_scores = tuple(
            score - PORTFOLIO_OVERLAP_PENALTY * usage
            for score, usage in zip(resolved_scores, usage_counts, strict=True)
        )
        ticket = _best_nonduplicate_ticket(adjusted_scores, existing)
        portfolio.append(ticket)
        existing.add(ticket)
        for number in ticket:
            usage_counts[number - NUMBER_MIN] += 1
    return tuple(portfolio)


def predict_tickets(
    history: DrawHistory,
    *,
    ticket_count: int,
    window_size: int,
    half_life: float,
) -> Portfolio:
    """Pure candidate entry point for an already-causal history."""

    scores = bayes_shrunk_recency_scores(
        history,
        window_size=window_size,
        half_life=half_life,
    )
    return portfolio_from_scores(scores, ticket_count=ticket_count)


def predict_target_scores(
    draws: DrawHistory,
    *,
    target_index: int,
    window_size: int,
    half_life: float,
) -> tuple[float, ...]:
    """Estimate scores at a target using only rows with a lower index.

    The target row is intentionally not inspected. Replacing its outcome or
    appending later outcomes therefore cannot change these scores.
    """

    if type(target_index) is not int or not 0 <= target_index < len(draws):
        raise BayesRecencyCandidateError("target_index must identify a draw in draws")
    return bayes_shrunk_recency_scores(
        draws[:target_index],
        window_size=window_size,
        half_life=half_life,
    )


def predict_target_tickets(
    draws: DrawHistory,
    *,
    target_index: int,
    ticket_count: int,
    window_size: int,
    half_life: float,
) -> Portfolio:
    """Predict at a target using only rows with a lower index."""

    return portfolio_from_scores(
        predict_target_scores(
            draws,
            target_index=target_index,
            window_size=window_size,
            half_life=half_life,
        ),
        ticket_count=ticket_count,
    )


__all__ = [
    "BASE_RATE",
    "BETA_PRIOR_STRENGTH",
    "DECAY_HALF_LIFE_MULTIPLIERS",
    "MAX_HALF_LIFE",
    "MIN_HALF_LIFE",
    "NUMBER_MAX",
    "NUMBER_MIN",
    "PICK_COUNT",
    "PORTFOLIO_OVERLAP_PENALTY",
    "SUPPORTED_TICKET_COUNTS",
    "SUPPORTED_WINDOWS",
    "BayesRecencyCandidateError",
    "bayes_shrunk_recency_scores",
    "portfolio_from_scores",
    "predict_target_scores",
    "predict_target_tickets",
    "predict_tickets",
]
