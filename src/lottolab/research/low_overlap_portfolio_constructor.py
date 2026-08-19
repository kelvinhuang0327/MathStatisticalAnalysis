"""A caller-controlled, candidate-driven low-overlap ticket portfolio
constructor -- generalizes the sealed `greedy_min_overlap_portfolio`
(`greedy_min_overlap_constructor.py`) from "enumerate the full legal
space" to "select a low-overlap legal subset of any upstream candidate
pool," optionally guided by an upstream predictive score.

This is `STRATEGY_MATRIX_PHASE5_GEOMETRY_ONLY_PORTFOLIO_APPLICATION_R1`.
It turns the already-sealed low-overlap geometry finding (arm B beats
random at every tested k>1 in all three native lotteries -- see
`docs/research/matrix-native-results/strategy-matrix-phase5-non-sidon-low-overlap-cross-lottery-synthesis-v1-report.md`)
into a reusable capability. It is NOT a new number predictor: it never
trains, fits, or reads any predictive model, and it never reads a draw
outcome, a replay session, or a database.

Two modes, selected only by whether `optional_scores` is given:

  GEOMETRY_ONLY (`optional_scores=None`)
      Pure legal low-overlap selection. If `candidates` is also `None`,
      this delegates directly to the unmodified, sealed
      `greedy_min_overlap_portfolio` over the lottery's full legal space
      -- true reuse, not a reimplementation. If `candidates` is a
      concrete upstream ticket list, this runs the same min-max-overlap
      greedy rule restricted to (and lexicographically ordered within)
      that candidate pool.

  SCORE_PLUS_GEOMETRY (`optional_scores` given)
      Requires an explicit `candidates` list the same length as
      `optional_scores`. Candidate priority is by descending score
      (ties broken lexicographically for determinism), but the same
      min-max-overlap greedy rule still governs which candidate is
      actually picked at each step -- a high score alone cannot force a
      pick that collapses the portfolio into near-duplicate tickets.
      `optional_scores` is only ever read, never written back.

`k` is always a caller-supplied exposure parameter -- this module names
no "best k," runs no threshold search, and adds no ticket beyond `k`.
Every returned ticket is validated against `lottery_rules` (a
`LotteryRuleContract`, main numbers only -- Zone-2/special numbers are
out of scope here, consistent with the rest of the
greedy_min_overlap_constructor family) before being returned; an
illegal candidate or a `k` beyond the unique legal candidate count is a
`ValueError`, never a silently short portfolio.

CLAIM BOUNDARY -- may say: `LOW_OVERLAP_PORTFOLIO_GEOMETRY_SUPPORTED`.
May NOT say: single-ticket predictive edge, future-number prediction
improved, profitability improved, or payout EV improved. Spending more
tickets always costs more tickets; nothing here represents that cost as
a strategy improvement.
"""

from __future__ import annotations

import itertools
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from lottolab.domain.lottery_rules import LotteryRuleContract
from lottolab.research.greedy_min_overlap_constructor import greedy_min_overlap_portfolio


@dataclass(frozen=True, slots=True)
class PortfolioGeometryMetrics:
    """The GEOMETRY OBJECTIVES for one concrete, already-built portfolio.

    Descriptive only: computing these never influences how the portfolio
    was built. `overlap_profile` maps `overlap_size -> pair_count` over
    every ticket pair. `coverage_concentration` is the population
    standard deviation of per-number use counts across the lottery's
    full main-number pool (0 for numbers never used).
    """

    max_pairwise_overlap: int
    mean_pairwise_overlap: float
    overlap_profile: Mapping[int, int]
    union_size: int
    coverage_concentration: float
    duplicate_tickets: int
    duplicate_pair_exposure: int
    duplicate_triple_exposure: int


def build_low_overlap_portfolio(
    candidates: Sequence[Sequence[int]] | None,
    k: int,
    lottery_rules: LotteryRuleContract,
    optional_scores: Sequence[float] | None = None,
) -> tuple[tuple[int, ...], ...]:
    """The `k` main-number tickets selected by the greedy min-max-overlap
    rule: restricted to legal, deduplicated candidates when `candidates`
    is given (priority order by descending `optional_scores` when
    supplied, else lexicographic), or over the full legal space -- via
    the sealed `greedy_min_overlap_portfolio` -- when `candidates` is
    `None`.

    Raises `ValueError` for a non-integer/negative `k`, an illegal or
    wrong-shaped candidate, a length mismatch between `candidates` and
    `optional_scores`, `optional_scores` given without `candidates`, or
    a `k` that exceeds the number of unique legal candidates available.
    Raises `TypeError` when `lottery_rules` is not a `LotteryRuleContract`.
    """

    if type(lottery_rules) is not LotteryRuleContract:
        raise TypeError("lottery_rules must be a LotteryRuleContract")
    if type(k) is not int or k < 0:
        raise ValueError("k must be a non-negative integer")

    draw_size = lottery_rules.main_number_count
    pool_min = lottery_rules.main_number_min
    pool_max = lottery_rules.main_number_max

    if candidates is None:
        if optional_scores is not None:
            raise ValueError("optional_scores requires an explicit candidates list")
        if pool_min != 1:
            raise ValueError("full-space delegation requires lottery_rules.main_number_min == 1")
        return greedy_min_overlap_portfolio(pool_max, draw_size, k)

    candidate_list = list(candidates)
    if optional_scores is not None and len(optional_scores) != len(candidate_list):
        raise ValueError("optional_scores must be the same length as candidates")
    if optional_scores is not None:
        for index, score in enumerate(optional_scores):
            if type(score) is not int and type(score) is not float:
                raise ValueError(f"optional_scores[{index}] must be numeric")

    canonical = [
        _canonical_legal_ticket(raw_ticket, index, lottery_rules)
        for index, raw_ticket in enumerate(candidate_list)
    ]

    unique_indices: list[int] = []
    seen: set[tuple[int, ...]] = set()
    for index, ticket in enumerate(canonical):
        if ticket not in seen:
            seen.add(ticket)
            unique_indices.append(index)

    if k > len(unique_indices):
        raise ValueError(
            f"k={k} exceeds {len(unique_indices)} unique legal candidates available"
        )

    if optional_scores is None:
        priority = sorted(unique_indices, key=lambda i: canonical[i])
    else:
        priority = sorted(unique_indices, key=lambda i: (-optional_scores[i], canonical[i]))

    remaining = [canonical[i] for i in priority]
    portfolio: list[tuple[int, ...]] = []
    for _ in range(k):
        best_index = 0
        best_overlap = draw_size + 1
        for index, ticket in enumerate(remaining):
            worst = max((len(set(ticket) & set(chosen)) for chosen in portfolio), default=0)
            if worst < best_overlap:
                best_overlap = worst
                best_index = index
                if worst == 0:
                    break
        portfolio.append(remaining.pop(best_index))

    return tuple(portfolio)


def _canonical_legal_ticket(
    raw_ticket: Sequence[int], index: int, lottery_rules: LotteryRuleContract
) -> tuple[int, ...]:
    draw_size = lottery_rules.main_number_count
    pool_min = lottery_rules.main_number_min
    pool_max = lottery_rules.main_number_max

    ticket = tuple(raw_ticket)
    if len(ticket) != draw_size:
        raise ValueError(f"candidate {index} does not have {draw_size} numbers: {ticket!r}")
    if any(type(number) is not int for number in ticket):
        raise ValueError(f"candidate {index} contains a non-integer number: {ticket!r}")
    if lottery_rules.main_numbers_unique and len(set(ticket)) != len(ticket):
        raise ValueError(f"candidate {index} has a duplicate number: {ticket!r}")
    if any(number < pool_min or number > pool_max for number in ticket):
        raise ValueError(
            f"candidate {index} has a number outside [{pool_min}, {pool_max}]: {ticket!r}"
        )
    return tuple(sorted(ticket))


def compute_portfolio_geometry_metrics(
    portfolio: Sequence[Sequence[int]],
    lottery_rules: LotteryRuleContract,
) -> PortfolioGeometryMetrics:
    """The GEOMETRY OBJECTIVES for an already-built portfolio: pairwise
    ticket overlap, union size, duplicate pair/triple exposure, and
    coverage concentration. Read-only -- never used to build a
    portfolio, only to describe one that already exists.
    """

    tickets = [tuple(sorted(ticket)) for ticket in portfolio]
    pool_min = lottery_rules.main_number_min
    pool_max = lottery_rules.main_number_max

    pairs = list(itertools.combinations(tickets, 2))
    overlaps = [len(set(a) & set(b)) for a, b in pairs]
    max_pairwise_overlap = max(overlaps, default=0)
    mean_pairwise_overlap = (sum(overlaps) / len(overlaps)) if overlaps else 0.0
    overlap_profile: dict[int, int] = {}
    for overlap in overlaps:
        overlap_profile[overlap] = overlap_profile.get(overlap, 0) + 1

    number_use_counts = dict.fromkeys(range(pool_min, pool_max + 1), 0)
    for ticket in tickets:
        for number in ticket:
            if number in number_use_counts:
                number_use_counts[number] += 1
    union_size = sum(1 for count in number_use_counts.values() if count >= 1)
    coverage_concentration = statistics.pstdev(number_use_counts.values())

    pair_counts: dict[tuple[int, int], int] = {}
    triple_counts: dict[tuple[int, int, int], int] = {}
    for ticket in tickets:
        for pair in itertools.combinations(ticket, 2):
            pair_counts[pair] = pair_counts.get(pair, 0) + 1
        for triple in itertools.combinations(ticket, 3):
            triple_counts[triple] = triple_counts.get(triple, 0) + 1
    duplicate_pair_exposure = sum(1 for count in pair_counts.values() if count >= 2)
    duplicate_triple_exposure = sum(1 for count in triple_counts.values() if count >= 2)
    duplicate_tickets = len(tickets) - len(set(tickets))

    return PortfolioGeometryMetrics(
        max_pairwise_overlap=max_pairwise_overlap,
        mean_pairwise_overlap=mean_pairwise_overlap,
        overlap_profile=overlap_profile,
        union_size=union_size,
        coverage_concentration=coverage_concentration,
        duplicate_tickets=duplicate_tickets,
        duplicate_pair_exposure=duplicate_pair_exposure,
        duplicate_triple_exposure=duplicate_triple_exposure,
    )
