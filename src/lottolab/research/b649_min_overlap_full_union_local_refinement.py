"""One frozen K10 one-swap ascent from the MIN_OVERLAP baseline.

The selection score integrates the special ball exactly over a fixed sample
of main draws. Final probabilities are computed by the existing exact scorer
in the separate research runner.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np

from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_OUTRIGHT_MATCHES,
    BIG_LOTTO_POOL_SIZE,
    DrawMasks,
    ticket_mask,
)

K: Final = 10
SELECTION_SEED: Final = 20260923
SELECTION_DRAW_COUNT: Final = 65_536
ITERATION_CAP: Final = 4
SELECTOR_ID: Final = "B649_MIN_OVERLAP_FULL_UNION_LOCAL_REFINEMENT_R1"

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]


@dataclass(frozen=True, slots=True)
class RefinementResult:
    """One deterministic selection, with sample counts kept separate from exact results."""

    portfolio: Portfolio
    selected_indices: tuple[int, ...]
    swaps: tuple[tuple[int, int, int], ...]
    initial_sample_outcome_count: int
    final_sample_outcome_count: int
    sample_draw_count: int
    stopped_by: str

    @property
    def swap_count(self) -> int:
        return len(self.swaps)


def refine_min_overlap_k10(
    full_union: Sequence[Sequence[int]],
    frozen_baseline: Sequence[Sequence[int]],
    *,
    selection_draws: DrawMasks,
    pool_size: int = BIG_LOTTO_POOL_SIZE,
    draw_size: int = BIG_LOTTO_DRAW_SIZE,
    outright_matches: int = BIG_LOTTO_OUTRIGHT_MATCHES,
) -> RefinementResult:
    """Apply at most four strictly improving one-for-one swaps to frozen K10.

    Every iteration scores every one-swap neighbor. Ties use the lowest
    baseline/current portfolio position, then the lowest full-union position.
    Only the main-draw sample is used for selection; no target result enters.
    """

    if not 1 <= outright_matches <= draw_size < pool_size <= 64:
        raise ValueError("illegal draw-space configuration")
    if len(frozen_baseline) != K or len(full_union) < K:
        raise ValueError("K10 baseline and full union must contain at least ten tickets")

    def canonical_ticket(candidate: Sequence[int]) -> Ticket:
        ticket = tuple(candidate)
        if (
            len(ticket) != draw_size
            or len(set(ticket)) != draw_size
            or any(type(number) is not int or not 1 <= number <= pool_size for number in ticket)
        ):
            raise ValueError("illegal candidate ticket")
        return tuple(sorted(ticket))

    union = tuple(canonical_ticket(ticket) for ticket in full_union)
    baseline = tuple(canonical_ticket(ticket) for ticket in frozen_baseline)
    if len(set(union)) != len(union) or len(set(baseline)) != K:
        raise ValueError("duplicate ticket in full union or K10 baseline")
    index_by_ticket = {ticket: index for index, ticket in enumerate(union)}
    if not set(baseline).issubset(index_by_ticket):
        raise ValueError("frozen K10 baseline is outside the full PRE_DRAW union")

    draws = np.asarray(selection_draws, dtype=np.uint64)
    if draws.ndim != 1 or draws.size == 0:
        raise ValueError("selection_draws must be a non-empty one-dimensional array")
    if np.any(np.bitwise_count(draws) != draw_size) or np.any(draws >> np.uint64(pool_size)):
        raise ValueError("selection_draws contain an illegal main draw")

    masks = np.asarray([ticket_mask(ticket) for ticket in union], dtype=np.uint64)
    hits = np.bitwise_count(masks[:, None] & draws[None, :])
    direct = hits >= outright_matches
    rescue = np.where(
        hits == outright_matches - 1,
        masks[:, None] & ~draws[None, :],
        np.uint64(0),
    )
    special_count = pool_size - draw_size

    def score(indices: Sequence[int]) -> int:
        direct_union = np.any(direct[list(indices)], axis=0)
        rescue_union = np.bitwise_or.reduce(rescue[list(indices)], axis=0)
        return int(
            np.where(direct_union, special_count, np.bitwise_count(rescue_union)).sum(
                dtype=np.int64
            )
        )

    selected = [index_by_ticket[ticket] for ticket in baseline]
    initial_count = score(selected)
    current_count = initial_count
    swaps: list[tuple[int, int, int]] = []
    stopped_by = "ITERATION_CAP"

    for _ in range(ITERATION_CAP):
        available = [index for index in range(len(union)) if index not in selected]
        best_count = current_count
        best_move: tuple[int, int] | None = None
        for remove_position in range(K):
            retained = selected[:remove_position] + selected[remove_position + 1 :]
            retained_direct = np.any(direct[retained], axis=0)
            retained_rescue = np.bitwise_or.reduce(rescue[retained], axis=0)
            neighbor_direct = direct[available] | retained_direct[None, :]
            neighbor_rescue = rescue[available] | retained_rescue[None, :]
            counts = np.where(
                neighbor_direct,
                special_count,
                np.bitwise_count(neighbor_rescue),
            ).sum(axis=1, dtype=np.int64)
            for add_position, candidate_count in enumerate(counts):
                if int(candidate_count) > best_count:
                    best_count = int(candidate_count)
                    best_move = remove_position, available[add_position]

        if best_move is None:
            stopped_by = "NO_IMPROVING_SWAP"
            break
        remove_position, add_index = best_move
        removed_index = selected[remove_position]
        selected[remove_position] = add_index
        swaps.append((removed_index, add_index, best_count - current_count))
        current_count = best_count

    if current_count != score(selected):
        raise AssertionError("one-swap sample score accounting diverged")
    return RefinementResult(
        portfolio=tuple(union[index] for index in selected),
        selected_indices=tuple(selected),
        swaps=tuple(swaps),
        initial_sample_outcome_count=initial_count,
        final_sample_outcome_count=current_count,
        sample_draw_count=int(draws.size),
        stopped_by=stopped_by,
    )
