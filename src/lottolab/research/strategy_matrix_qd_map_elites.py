"""Smallest deterministic native MAP-Elites / Quality-Diversity portfolio
explorer for BIG_LOTTO K5 (`STRATEGY_MATRIX_NATIVE_MAP_ELITES_QD_PROTOTYPE_R1`).

Reuses, never reimplements, three existing sealed primitives:
- `exact_coverage_fast_evaluator.fast_exact_portfolio_coverage` /
  `coverage_with_base` / `portfolio_qualifying_draws` / `clear_cache` for the
  quality objective (exact `minimum_matches`+ portfolio coverage) and its
  proven per-slot cache-bounding pattern.
- `reference_e_exact_one_exchange_refinement.legal_one_exchange_tickets` /
  `canonicalize_portfolio` / `canonicalize_ticket` for the deterministic
  emitter (legal one-number-exchange neighborhood) and canonical portfolio
  ordering/tie-break.
- `low_overlap_portfolio_constructor.compute_portfolio_geometry_metrics` for
  the R1 descriptor space (`max_pairwise_overlap`, `union_size`).

Algorithm -- one generation only, no RNG, no frontier queue: every frozen
seed's complete legal one-exchange neighborhood is emitted and evaluated
exactly once, in fixed deterministic order (seed order, then slot order,
then `legal_one_exchange_tickets`'s own deterministic order), against a
caller-supplied `evaluation_budget`. Newly discovered elites are never
themselves expanded -- there is no second generation. `evaluation_budget` is
a hard stop, checked before every candidate evaluation, and is never
escalated automatically. This is deliberate: the governing packet requires
"do not silently grow generations/evaluations," and a single fixed-size wave
from each seed is the smallest design that can answer the R1 research
question.

One elite occupies each descriptor cell: a candidate replaces the current
occupant only if its exact quality is strictly higher, or exactly tied and
its canonical portfolio sorts lexicographically smaller. Seed portfolios are
seeded into the archive first (also subject to the same replacement/tie-break
rule against each other), and `seed_descriptor_cells` is snapshotted
immediately afterward -- strictly before any neighbor is evaluated.

CLAIM BOUNDARY -- may say: new morphology discovered; exact uniform-draw
coverage improved, tied, or degraded; bounded execution cost. May NOT say:
prediction success improved, out-of-sample edge proven, future-number
prediction improved, profitability improved, or a new strategy family
proven. This module never reads a draw outcome, a replay session, or a
database.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction

from lottolab.domain.lottery_rules import LotteryRuleContract
from lottolab.research.exact_coverage_fast_evaluator import (
    clear_cache,
    coverage_with_base,
    fast_exact_portfolio_coverage,
    portfolio_qualifying_draws,
)
from lottolab.research.low_overlap_portfolio_constructor import compute_portfolio_geometry_metrics
from lottolab.research.reference_e_exact_one_exchange_refinement import (
    canonicalize_portfolio,
    legal_one_exchange_tickets,
)

Ticket = tuple[int, ...]
Portfolio = tuple[Ticket, ...]
DescriptorCell = tuple[int, int]  # (max_pairwise_overlap, union_size)


@dataclass(frozen=True)
class EliteEntry:
    """One archive occupant: the portfolio currently holding its cell."""

    portfolio: Portfolio
    quality: Fraction
    is_seed: bool


@dataclass(frozen=True)
class MapElitesResult:
    """Full outcome of one bounded, single-generation MAP-Elites run."""

    seed_count: int
    seed_descriptor_cells: frozenset[DescriptorCell]
    final_descriptor_cells: frozenset[DescriptorCell]
    archive: Mapping[DescriptorCell, EliteEntry]
    evaluated_candidate_count: int
    evaluation_budget: int
    budget_exhausted: bool

    @property
    def new_descriptor_cell_count(self) -> int:
        """`final_descriptor_cells` minus `seed_descriptor_cells` -- a
        non-seed portfolio landing in an already-seeded cell is NOT a new
        niche; only a genuinely new descriptor coordinate counts.
        """
        return len(self.final_descriptor_cells - self.seed_descriptor_cells)

    @property
    def non_seed_elite_count(self) -> int:
        """Archive cells whose *current* occupant is not one of the input
        seed portfolios -- includes both brand-new cells and seed cells a
        neighbor has out-competed.
        """
        return sum(1 for entry in self.archive.values() if not entry.is_seed)

    @property
    def best_quality(self) -> Fraction:
        return max(entry.quality for entry in self.archive.values())


def portfolio_descriptor_cell(
    portfolio: Portfolio, lottery_rules: LotteryRuleContract
) -> DescriptorCell:
    """R1 descriptor coordinates for one already-canonical portfolio."""
    metrics = compute_portfolio_geometry_metrics(portfolio, lottery_rules)
    return (metrics.max_pairwise_overlap, metrics.union_size)


def _validate_seed(
    portfolio: Portfolio, pool_size: int, draw_size: int
) -> Portfolio:
    try:
        canonical = canonicalize_portfolio(portfolio)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"portfolio is not a legal canonicalizable value: {portfolio!r}") from exc
    for ticket in canonical:
        if any(type(number) is not int for number in ticket):
            raise ValueError(f"ticket contains a non-integer number: {ticket}")
        if len(ticket) != draw_size:
            raise ValueError(
                f"ticket length {len(ticket)} does not match draw_size {draw_size}: {ticket}"
            )
        if any(number < 1 or number > pool_size for number in ticket):
            raise ValueError(f"ticket number out of range 1..{pool_size}: {ticket}")
    return canonical


def run_map_elites(
    seeds: Sequence[Portfolio],
    lottery_rules: LotteryRuleContract,
    minimum_matches: int,
    evaluation_budget: int,
) -> MapElitesResult:
    """Run the bounded, single-generation, deterministic QD explorer.

    `seeds` must contain at least one legal portfolio (draw-size tickets,
    numbers in `1..pool_size`, no duplicate tickets within a portfolio, no
    duplicate portfolios across `seeds`); any violation fails closed with
    `ValueError` before any evaluation runs. `pool_size`/`draw_size` are read
    from `lottery_rules` (`main_number_min` must be 1, matching the
    `1..pool_size` numbering every reused coverage primitive assumes).
    """
    if lottery_rules.main_number_min != 1:
        raise ValueError("lottery_rules.main_number_min must be 1")
    if evaluation_budget < 0:
        raise ValueError("evaluation_budget must be >= 0")
    if len(seeds) == 0:
        raise ValueError("at least one seed portfolio is required")

    pool_size = lottery_rules.main_number_max
    draw_size = lottery_rules.main_number_count

    canonical_seeds = [_validate_seed(seed, pool_size, draw_size) for seed in seeds]
    if len(set(canonical_seeds)) != len(canonical_seeds):
        raise ValueError("duplicate seed portfolios are not allowed")

    archive: dict[DescriptorCell, EliteEntry] = {}

    def consider(portfolio: Portfolio, quality: Fraction, *, is_seed: bool) -> None:
        cell = portfolio_descriptor_cell(portfolio, lottery_rules)
        existing = archive.get(cell)
        if (
            existing is None
            or quality > existing.quality
            or (quality == existing.quality and portfolio < existing.portfolio)
        ):
            archive[cell] = EliteEntry(portfolio=portfolio, quality=quality, is_seed=is_seed)

    for seed in canonical_seeds:
        seed_quality = fast_exact_portfolio_coverage(pool_size, draw_size, minimum_matches, seed)
        consider(seed, seed_quality, is_seed=True)
    clear_cache()

    # Snapshot BEFORE any neighbor is evaluated -- required ordering.
    seed_descriptor_cells = frozenset(archive.keys())

    evaluated_candidate_count = 0
    budget_exhausted = False
    for seed in canonical_seeds:
        if budget_exhausted:
            break
        seed_ticket_set = set(seed)
        for slot_index, original_ticket in enumerate(seed):
            if budget_exhausted:
                break
            remaining_tickets = seed[:slot_index] + seed[slot_index + 1 :]
            base_draws = portfolio_qualifying_draws(
                pool_size, draw_size, minimum_matches, remaining_tickets
            )
            for mutated_ticket in legal_one_exchange_tickets(pool_size, original_ticket):
                if mutated_ticket in seed_ticket_set:
                    continue  # illegal duplicate -- pre-filtered, not an evaluation
                if evaluated_candidate_count >= evaluation_budget:
                    budget_exhausted = True
                    break
                neighbor = canonicalize_portfolio((*remaining_tickets, mutated_ticket))
                quality = coverage_with_base(
                    pool_size, draw_size, minimum_matches, base_draws, mutated_ticket
                )
                evaluated_candidate_count += 1
                consider(neighbor, quality, is_seed=False)
            clear_cache()  # per-slot boundary -- bounds peak memory to one slot

    final_descriptor_cells = frozenset(archive.keys())

    return MapElitesResult(
        seed_count=len(canonical_seeds),
        seed_descriptor_cells=seed_descriptor_cells,
        final_descriptor_cells=final_descriptor_cells,
        archive=dict(archive),
        evaluated_candidate_count=evaluated_candidate_count,
        evaluation_budget=evaluation_budget,
        budget_exhausted=budget_exhausted,
    )
