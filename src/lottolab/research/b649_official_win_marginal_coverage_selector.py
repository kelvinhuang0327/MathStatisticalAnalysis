"""Frozen B649 official-win marginal-coverage selector, version 1.

The selector greedily chooses the ticket with the largest incremental
OFFICIAL_ANY_PRIZE coverage on one fixed, seeded main-draw sample. The special
ball is integrated exactly for each sampled main draw. Final model evaluation
is deliberately performed separately with the exhaustive exact evaluator.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Final

import numpy as np

from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_OUTRIGHT_MATCHES,
    BIG_LOTTO_POOL_SIZE,
    DrawMasks,
    ticket_mask,
)

PRIMARY_K: Final = 10
SECONDARY_K: Final = 20
SELECTION_DRAW_COUNT: Final = 65_536
SELECTION_SEED: Final = 20260923
SELECTOR_ID: Final = "B649_OFFICIAL_WIN_MARGINAL_COVERAGE_V1"
EVENT_ID: Final = "OFFICIAL_ANY_PRIZE"
MODEL_ID: Final = "BIG_LOTTO_UNIFORM_FAIR_DRAW"

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]


@dataclass(frozen=True, slots=True)
class SelectorSpec:
    """Immutable, reportable settings for the frozen K10 selector."""

    selector_id: str
    event_id: str
    model_id: str
    primary_k: int
    selection_draw_count: int
    selection_seed: int
    tie_break: str
    special_ball_handling: str


FROZEN_K10_SPEC: Final = SelectorSpec(
    selector_id=SELECTOR_ID,
    event_id=EVENT_ID,
    model_id=MODEL_ID,
    primary_k=PRIMARY_K,
    selection_draw_count=SELECTION_DRAW_COUNT,
    selection_seed=SELECTION_SEED,
    tie_break="EARLIEST_CANDIDATE_POOL_POSITION",
    special_ball_handling="ANALYTIC_UNION_PER_SAMPLED_MAIN_DRAW",
)


@dataclass(frozen=True, slots=True)
class SelectionResult:
    """Selected tickets and the deterministic evidence used at selection time."""

    selected_indices: tuple[int, ...]
    portfolio: Portfolio
    marginal_sample_outcome_counts: tuple[int, ...]
    sample_official_any_prize_probability: Fraction
    sample_draw_count: int


def generate_selection_draw_sample(
    *,
    sample_count: int = SELECTION_DRAW_COUNT,
    seed: int = SELECTION_SEED,
    pool_size: int = BIG_LOTTO_POOL_SIZE,
    draw_size: int = BIG_LOTTO_DRAW_SIZE,
) -> DrawMasks:
    """Create a reproducible uniform sample of distinct-number main draws."""

    if not 1 <= draw_size < pool_size <= 64:
        raise ValueError("draw space must satisfy 1 <= draw_size < pool_size <= 64")
    if sample_count <= 0:
        raise ValueError("sample_count must be positive")

    random = np.random.default_rng(seed)
    keys = random.random((sample_count, pool_size), dtype=np.float32)
    numbers = np.argpartition(keys, draw_size - 1, axis=1)[:, :draw_size]
    number_bits = np.left_shift(np.uint64(1), numbers.astype(np.uint64, copy=False))
    return np.bitwise_or.reduce(number_bits, axis=1, dtype=np.uint64)


def select_official_win_marginal_coverage(
    candidate_pool: Sequence[Sequence[int]],
    k: int,
    *,
    selection_draws: DrawMasks,
    pool_size: int = BIG_LOTTO_POOL_SIZE,
    draw_size: int = BIG_LOTTO_DRAW_SIZE,
    outright_matches: int = BIG_LOTTO_OUTRIGHT_MATCHES,
) -> SelectionResult:
    """Greedily select exactly ``k`` tickets by marginal official-win coverage.

    The candidate pool is treated as immutable and in-order. Equal marginal
    gains are resolved by original candidate-pool position. The special ball
    is integrated analytically: an outright hit covers every legal special;
    otherwise, tickets with ``outright_matches - 1`` main hits cover the union
    of their undrawn ticket numbers.
    """

    if not candidate_pool:
        raise ValueError("candidate_pool must not be empty")
    if not 1 <= k <= len(candidate_pool):
        raise ValueError("k must be between 1 and the candidate pool size")
    if not 1 <= outright_matches <= draw_size < pool_size <= 64:
        raise ValueError("draw space must satisfy 1 <= outright <= draw < pool <= 64")
    if selection_draws.ndim != 1 or selection_draws.size == 0:
        raise ValueError("selection_draws must be a non-empty one-dimensional array")

    canonical_tickets: list[Ticket] = []
    canonical_keys: set[Ticket] = set()
    masks: list[np.uint64] = []
    for index, candidate in enumerate(candidate_pool):
        ticket = tuple(candidate)
        if (
            len(ticket) != draw_size
            or len(set(ticket)) != draw_size
            or any(type(number) is not int or not 1 <= number <= pool_size for number in ticket)
        ):
            raise ValueError(f"illegal candidate ticket at index {index}")
        canonical_key = tuple(sorted(ticket))
        if canonical_key in canonical_keys:
            raise ValueError(f"duplicate candidate ticket at index {index}")
        canonical_keys.add(canonical_key)
        canonical_tickets.append(ticket)
        masks.append(np.uint64(ticket_mask(ticket)))

    draws = np.asarray(selection_draws, dtype=np.uint64)
    draw_popcounts = np.bitwise_count(draws)
    if np.any(draw_popcounts != draw_size) or np.any(draws >> np.uint64(pool_size)):
        raise ValueError("selection_draws contain an illegal main draw")

    candidate_masks = np.asarray(masks, dtype=np.uint64)
    hits = np.bitwise_count(draws[:, None] & candidate_masks[None, :]).astype(np.uint8)
    direct_wins = hits >= outright_matches
    rescue_masks = np.where(
        outright_matches - 1 == hits.T,
        candidate_masks[:, None] & ~draws[None, :],
        np.uint64(0),
    )

    special_count = pool_size - draw_size
    covered_direct = np.zeros(draws.size, dtype=np.bool_)
    covered_rescue = np.zeros(draws.size, dtype=np.uint64)
    selected_indices: list[int] = []
    marginal_counts: list[int] = []
    available = np.ones(len(canonical_tickets), dtype=np.bool_)

    for _ in range(k):
        new_direct = direct_wins & ~covered_direct[:, None]
        prior_rescue_counts = np.bitwise_count(covered_rescue)
        newly_covered_special_counts = special_count - prior_rescue_counts
        direct_gains = (new_direct * newly_covered_special_counts[:, None]).sum(
            axis=0, dtype=np.int64
        )

        new_rescue = np.where(
            covered_direct[None, :],
            np.uint64(0),
            rescue_masks & ~covered_rescue[None, :],
        )
        rescue_gains = np.bitwise_count(new_rescue).sum(axis=1, dtype=np.int64)
        marginal_gains = direct_gains + rescue_gains
        marginal_gains[~available] = -1

        best_index = min(
            (int(index) for index in np.flatnonzero(available)),
            key=lambda index: (-int(marginal_gains[index]), index),
        )
        selected_indices.append(best_index)
        marginal_counts.append(int(marginal_gains[best_index]))
        available[best_index] = False
        covered_direct |= direct_wins[:, best_index]
        covered_rescue |= rescue_masks[best_index]

    current_outcome_count = int(
        np.where(
            covered_direct,
            special_count,
            np.bitwise_count(covered_rescue),
        ).sum(dtype=np.int64)
    )
    if sum(marginal_counts) != current_outcome_count:
        raise AssertionError("marginal coverage accounting diverged from selected coverage")

    return SelectionResult(
        selected_indices=tuple(selected_indices),
        portfolio=tuple(canonical_tickets[index] for index in selected_indices),
        marginal_sample_outcome_counts=tuple(marginal_counts),
        sample_official_any_prize_probability=Fraction(
            current_outcome_count, draws.size * special_count
        ),
        sample_draw_count=int(draws.size),
    )


__all__ = [
    "EVENT_ID",
    "FROZEN_K10_SPEC",
    "MODEL_ID",
    "PRIMARY_K",
    "SECONDARY_K",
    "SELECTION_DRAW_COUNT",
    "SELECTION_SEED",
    "SELECTOR_ID",
    "SelectionResult",
    "SelectorSpec",
    "generate_selection_draw_sample",
    "select_official_win_marginal_coverage",
]
