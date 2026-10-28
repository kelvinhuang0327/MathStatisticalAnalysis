"""Exact expected-maximum main-match scoring and K2/K3/K5 local search.

The objective is E[max_t |t ∩ D|] over all uniformly likely 6-number main
draws D from 1..49. It deliberately excludes the special number and every
official prize-tier rule.

The score uses a grouped-incidence dynamic program. Numbers are grouped by
which portfolio tickets contain them; selecting x numbers from a group of size
c contributes comb(c, x) draw subsets. Thus the integer numerator is exact
over all comb(pool_size, draw_size) main draws without enumerating them one by
one.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import comb

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]

BIG_LOTTO_POOL_SIZE = 49
BIG_LOTTO_DRAW_SIZE = 6
BIG_LOTTO_UNIT_COST_NTD = 50
K235_TICKET_COUNTS = (2, 3, 5)


@dataclass(frozen=True, slots=True)
class ExactExpectedMaxScore:
    """Exact integer outcome counts for expected maximum main matches."""

    draw_count: int
    maximum_match_sum: int
    threshold_draw_counts: tuple[int, ...]

    @property
    def expected_maximum(self) -> Fraction:
        """Exact E[max_t |t ∩ D|] as a reduced rational."""

        return Fraction(self.maximum_match_sum, self.draw_count)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "draw_count": self.draw_count,
            "maximum_match_sum": self.maximum_match_sum,
            "expected_max_main_matches_fraction": str(self.expected_maximum),
            "expected_max_main_matches": float(self.expected_maximum),
            "threshold_draw_counts": list(self.threshold_draw_counts),
            "tail_sum_fraction": str(
                sum(
                    (Fraction(count, self.draw_count) for count in self.threshold_draw_counts),
                    Fraction(0),
                )
            ),
        }


@dataclass(frozen=True, slots=True)
class ExactExpectedMaxUnionBound:
    """Exact hypergeometric tail counts for the universal union-bound ceiling."""

    draw_count: int
    single_ticket_tail_draw_counts: tuple[int, ...]
    portfolio_tail_upper_bound_draw_counts: tuple[int, ...]
    maximum_match_sum_upper_bound: int

    @property
    def expected_maximum_upper_bound(self) -> Fraction:
        return Fraction(self.maximum_match_sum_upper_bound, self.draw_count)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "draw_count": self.draw_count,
            "single_ticket_tail_draw_counts": list(self.single_ticket_tail_draw_counts),
            "portfolio_tail_upper_bound_draw_counts": list(
                self.portfolio_tail_upper_bound_draw_counts
            ),
            "maximum_match_sum_upper_bound": self.maximum_match_sum_upper_bound,
            "expected_maximum_upper_bound_fraction": str(self.expected_maximum_upper_bound),
        }


@dataclass(frozen=True, slots=True)
class LocalSearchResult:
    """One deterministic seeded single-ticket-replacement search."""

    start_portfolio: Portfolio
    start_score: ExactExpectedMaxScore
    portfolio: Portfolio
    score: ExactExpectedMaxScore
    evaluations: int
    passes: int
    converged: bool
    seed: int

    @property
    def improved(self) -> bool:
        return self.score.maximum_match_sum > self.start_score.maximum_match_sum


def _validate_draw_space(pool_size: int, draw_size: int) -> None:
    if type(pool_size) is not int or type(draw_size) is not int:
        raise ValueError("pool_size and draw_size must be integers")
    if not 1 <= draw_size <= pool_size <= 64:
        raise ValueError("draw space must satisfy 1 <= draw_size <= pool_size <= 64")


def _normalize_portfolio(
    portfolio: Sequence[Sequence[int]], pool_size: int, draw_size: int
) -> Portfolio:
    _validate_draw_space(pool_size, draw_size)
    if not isinstance(portfolio, (list, tuple)) or not portfolio:
        raise ValueError("portfolio must be a non-empty list or tuple")

    normalized: list[Ticket] = []
    for ticket in portfolio:
        if not isinstance(ticket, (list, tuple)):
            raise ValueError("each ticket must be a list or tuple")
        if len(ticket) != draw_size:
            raise ValueError(f"each ticket must contain exactly {draw_size} numbers")
        if any(type(number) is not int or not 1 <= number <= pool_size for number in ticket):
            raise ValueError(f"ticket numbers must be integers in 1..{pool_size}")
        if len(set(ticket)) != draw_size:
            raise ValueError("ticket numbers must be distinct")
        normalized.append(tuple(sorted(ticket)))
    return tuple(sorted(normalized))


def evaluate_expected_max_main_matches(
    pool_size: int,
    draw_size: int,
    portfolio: Sequence[Sequence[int]],
) -> ExactExpectedMaxScore:
    """Evaluate E[max ticket main-number matches] exactly by incidence DP.

    Each draw is a draw_size-subset of 1..pool_size. Repeated portfolio tickets
    are permitted by the scorer and naturally contribute no extra coverage;
    the local search itself emits distinct ticket lines.
    """

    normalized = _normalize_portfolio(portfolio, pool_size, draw_size)
    ticket_count = len(normalized)
    ticket_sets = tuple(set(ticket) for ticket in normalized)

    incidence_counts: Counter[int] = Counter()
    for number in range(1, pool_size + 1):
        incidence_pattern = 0
        for ticket_index, ticket_numbers in enumerate(ticket_sets):
            if number in ticket_numbers:
                incidence_pattern |= 1 << ticket_index
        incidence_counts[incidence_pattern] += 1

    # A state is (numbers selected so far, per-ticket hit counts). The state
    # value counts the actual draw subsets represented by that state.
    zero_hits = (0,) * ticket_count
    states: dict[tuple[int, tuple[int, ...]], int] = {(0, zero_hits): 1}
    for incidence_pattern, group_size in sorted(incidence_counts.items()):
        members = tuple(
            ticket_index
            for ticket_index in range(ticket_count)
            if incidence_pattern & (1 << ticket_index)
        )
        next_states: defaultdict[tuple[int, tuple[int, ...]], int] = defaultdict(int)
        for (selected, hits), represented_draws in states.items():
            largest_take = min(group_size, draw_size - selected)
            for take in range(largest_take + 1):
                updated_hits = hits
                if take and members:
                    hit_list = list(hits)
                    for ticket_index in members:
                        hit_list[ticket_index] += take
                    updated_hits = tuple(hit_list)
                state_key = (selected + take, updated_hits)
                next_states[state_key] += represented_draws * comb(group_size, take)
        states = dict(next_states)

    draw_count = comb(pool_size, draw_size)
    maximum_match_sum = 0
    threshold_draw_counts = [0] * draw_size
    enumerated_draw_count = 0
    for (selected, hits), represented_draws in states.items():
        if selected != draw_size:
            continue
        enumerated_draw_count += represented_draws
        maximum_hits = max(hits)
        maximum_match_sum += represented_draws * maximum_hits
        for threshold in range(1, draw_size + 1):
            if maximum_hits >= threshold:
                threshold_draw_counts[threshold - 1] += represented_draws

    if enumerated_draw_count != draw_count:
        raise AssertionError("incidence DP did not count every main draw exactly once")
    if sum(threshold_draw_counts) != maximum_match_sum:
        raise AssertionError("expected maximum does not equal its integer tail sum")

    return ExactExpectedMaxScore(
        draw_count=draw_count,
        maximum_match_sum=maximum_match_sum,
        threshold_draw_counts=tuple(threshold_draw_counts),
    )


def expected_max_union_bound_details(
    pool_size: int, draw_size: int, ticket_count: int
) -> ExactExpectedMaxUnionBound:
    """Expose exact single-ticket tails and the resulting portfolio union bound."""

    _validate_draw_space(pool_size, draw_size)
    if type(ticket_count) is not int or ticket_count < 1:
        raise ValueError("ticket_count must be a positive integer")

    draw_count = comb(pool_size, draw_size)
    single_ticket_tails = [
        sum(
            comb(draw_size, hits) * comb(pool_size - draw_size, draw_size - hits)
            for hits in range(threshold, draw_size + 1)
        )
        for threshold in range(1, draw_size + 1)
    ]
    portfolio_tail_bounds = [
        min(draw_count, ticket_count * tail_count) for tail_count in single_ticket_tails
    ]
    upper_bound_sum = sum(portfolio_tail_bounds)
    return ExactExpectedMaxUnionBound(
        draw_count=draw_count,
        single_ticket_tail_draw_counts=tuple(single_ticket_tails),
        portfolio_tail_upper_bound_draw_counts=tuple(portfolio_tail_bounds),
        maximum_match_sum_upper_bound=upper_bound_sum,
    )


def expected_max_union_bound(pool_size: int, draw_size: int, ticket_count: int) -> Fraction:
    """Union-bound ceiling: sum_m min(1, K * P(one ticket hits at least m))."""

    return expected_max_union_bound_details(
        pool_size, draw_size, ticket_count
    ).expected_maximum_upper_bound


def zero_overlap_incumbent(ticket_count: int) -> Portfolio:
    """Canonical representative of the fixed-K zero-overlap incumbent class."""

    if ticket_count not in K235_TICKET_COUNTS:
        raise ValueError(f"ticket_count must be one of {K235_TICKET_COUNTS}")
    return tuple(
        tuple(range(start, start + BIG_LOTTO_DRAW_SIZE))
        for start in range(1, ticket_count * BIG_LOTTO_DRAW_SIZE + 1, BIG_LOTTO_DRAW_SIZE)
    )


def portfolio_cost_ntd(ticket_count: int) -> int:
    """Official base cost for K Big Lotto single-line tickets."""

    if ticket_count not in K235_TICKET_COUNTS:
        raise ValueError(f"ticket_count must be one of {K235_TICKET_COUNTS}")
    return ticket_count * BIG_LOTTO_UNIT_COST_NTD


def _random_portfolio(
    rng: random.Random, ticket_count: int, pool_size: int, draw_size: int
) -> Portfolio:
    tickets: list[Ticket] = []
    seen: set[Ticket] = set()
    while len(tickets) < ticket_count:
        ticket = tuple(sorted(rng.sample(range(1, pool_size + 1), draw_size)))
        if ticket not in seen:
            seen.add(ticket)
            tickets.append(ticket)
    return tuple(sorted(tickets))


def _sample_replacement_tickets(
    rng: random.Random,
    *,
    pool_size: int,
    draw_size: int,
    sample_size: int,
    excluded: set[Ticket],
) -> tuple[Ticket, ...]:
    candidates: list[Ticket] = []
    seen = set(excluded)
    maximum_attempts = max(100, sample_size * 30)
    for _ in range(maximum_attempts):
        if len(candidates) >= sample_size:
            break
        ticket = tuple(sorted(rng.sample(range(1, pool_size + 1), draw_size)))
        if ticket not in seen:
            seen.add(ticket)
            candidates.append(ticket)
    return tuple(candidates)


def optimize_expected_max_local(
    start_portfolio: Sequence[Sequence[int]],
    *,
    pool_size: int = BIG_LOTTO_POOL_SIZE,
    draw_size: int = BIG_LOTTO_DRAW_SIZE,
    seed: int,
    candidate_samples_per_ticket: int = 12,
    max_passes: int = 2,
) -> LocalSearchResult:
    """Run seeded bounded single-ticket-replacement ascent for K2, K3, or K5."""

    start = _normalize_portfolio(start_portfolio, pool_size, draw_size)
    ticket_count = len(start)
    if ticket_count not in K235_TICKET_COUNTS:
        raise ValueError(f"local search supports K in {K235_TICKET_COUNTS}")
    if len(set(start)) != ticket_count:
        raise ValueError("local search requires distinct ticket lines")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if type(candidate_samples_per_ticket) is not int or candidate_samples_per_ticket < 1:
        raise ValueError("candidate_samples_per_ticket must be a positive integer")
    if type(max_passes) is not int or max_passes < 1:
        raise ValueError("max_passes must be a positive integer")

    current = start
    current_score = evaluate_expected_max_main_matches(pool_size, draw_size, current)
    evaluations = 1
    passes = 0
    converged = False
    rng = random.Random(seed)

    for pass_index in range(max_passes):
        passes = pass_index + 1
        improved_this_pass = False
        for slot, current_ticket in enumerate(current):
            excluded = set(current)
            excluded.discard(current_ticket)
            excluded.add(current_ticket)
            candidates = _sample_replacement_tickets(
                rng,
                pool_size=pool_size,
                draw_size=draw_size,
                sample_size=candidate_samples_per_ticket,
                excluded=excluded,
            )
            best_ticket = current_ticket
            best_score = current_score
            for candidate in candidates:
                trial = tuple(sorted((*current[:slot], candidate, *current[slot + 1 :])))
                candidate_score = evaluate_expected_max_main_matches(pool_size, draw_size, trial)
                evaluations += 1
                if candidate_score.maximum_match_sum > best_score.maximum_match_sum:
                    best_ticket = candidate
                    best_score = candidate_score
            if best_score.maximum_match_sum > current_score.maximum_match_sum:
                current = tuple(sorted((*current[:slot], best_ticket, *current[slot + 1 :])))
                current_score = best_score
                improved_this_pass = True
        if not improved_this_pass:
            converged = True
            break

    return LocalSearchResult(
        start_portfolio=start,
        start_score=evaluate_expected_max_main_matches(pool_size, draw_size, start),
        portfolio=current,
        score=current_score,
        evaluations=evaluations + 1,
        passes=passes,
        converged=converged,
        seed=seed,
    )


def run_k235_research_comparison(
    *,
    seed: int = 1028,
    random_baseline_count: int = 6,
    candidate_samples_per_ticket: int = 12,
    max_passes: int = 2,
) -> dict[str, object]:
    """Compare exact objective scores for K2/K3/K5 incumbents, random, and search."""

    if type(random_baseline_count) is not int or random_baseline_count < 1:
        raise ValueError("random_baseline_count must be a positive integer")
    results: list[dict[str, object]] = []
    for ticket_count in K235_TICKET_COUNTS:
        incumbent = zero_overlap_incumbent(ticket_count)
        incumbent_score = evaluate_expected_max_main_matches(
            BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE, incumbent
        )

        random_rng = random.Random(seed + 10_000 * ticket_count)
        random_portfolios = tuple(
            _random_portfolio(random_rng, ticket_count, BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE)
            for _ in range(random_baseline_count)
        )
        random_scores = tuple(
            evaluate_expected_max_main_matches(BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE, portfolio)
            for portfolio in random_portfolios
        )

        search_outcomes = []
        starts = (incumbent, *random_portfolios)
        for index, start in enumerate(starts):
            search_outcomes.append(
                optimize_expected_max_local(
                    start,
                    seed=seed + ticket_count * 100_000 + index,
                    candidate_samples_per_ticket=candidate_samples_per_ticket,
                    max_passes=max_passes,
                )
            )

        candidate_portfolio = incumbent
        candidate_score = incumbent_score
        for outcome in search_outcomes:
            if outcome.score.maximum_match_sum > candidate_score.maximum_match_sum:
                candidate_portfolio = outcome.portfolio
                candidate_score = outcome.score

        random_values = tuple(score.expected_maximum for score in random_scores)
        random_mean = sum(random_values, Fraction(0)) / len(random_values)
        results.append(
            {
                "ticket_count": ticket_count,
                "ticket_cost_ntd": portfolio_cost_ntd(ticket_count),
                "zero_overlap_incumbent": {
                    "label": "CANONICAL_ZERO_OVERLAP_REPRESENTATIVE",
                    "tickets": [list(ticket) for ticket in incumbent],
                    "score": incumbent_score.canonical_dict(),
                },
                "random_baselines": [
                    {
                        "tickets": [list(ticket) for ticket in portfolio],
                        "score": score.canonical_dict(),
                    }
                    for portfolio, score in zip(random_portfolios, random_scores, strict=True)
                ],
                "random_summary": {
                    "sample_count": random_baseline_count,
                    "minimum_fraction": str(min(random_values)),
                    "mean_fraction": str(random_mean),
                    "maximum_fraction": str(max(random_values)),
                },
                "candidate": {
                    "tickets": [list(ticket) for ticket in candidate_portfolio],
                    "score": candidate_score.canonical_dict(),
                    "status": (
                        "GAIN"
                        if candidate_score.maximum_match_sum > incumbent_score.maximum_match_sum
                        else "NO_GAIN"
                    ),
                    "delta_vs_incumbent_fraction": str(
                        candidate_score.expected_maximum - incumbent_score.expected_maximum
                    ),
                },
                "theoretical_union_bound": expected_max_union_bound_details(
                    BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE, ticket_count
                ).canonical_dict(),
                "search": {
                    "seed": seed,
                    "random_start_count": random_baseline_count,
                    "candidate_samples_per_ticket": candidate_samples_per_ticket,
                    "max_passes": max_passes,
                    "total_exact_evaluations": sum(
                        outcome.evaluations for outcome in search_outcomes
                    ),
                    "outcomes": [
                        {
                            "start_score_fraction": str(outcome.start_score.expected_maximum),
                            "final_score_fraction": str(outcome.score.expected_maximum),
                            "improved": outcome.improved,
                            "evaluations": outcome.evaluations,
                            "passes": outcome.passes,
                            "converged": outcome.converged,
                            "seed": outcome.seed,
                        }
                        for outcome in search_outcomes
                    ],
                },
            }
        )

    return {
        "objective": "EXPECTED_MAX_MAIN_MATCHES_V1",
        "objective_definition": (
            "E[max over tickets t of |t intersect D|], over all uniformly "
            "likely 6-number main draws D from 1..49"
        ),
        "outcome_space": "main numbers only; special number excluded",
        "draw_count": comb(BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE),
        "ticket_unit_cost_ntd": BIG_LOTTO_UNIT_COST_NTD,
        "zero_overlap_equivalence": (
            "For fixed K, every zero-overlap portfolio has the same score: "
            "its K disjoint six-number incidence classes and 49-6K outside "
            "numbers have identical cardinalities."
        ),
        "theoretical_limit": (
            "For each threshold m, P(max matches >= m) <= min(1, "
            "K * P(one six-number ticket matches >= m)); sum these exact "
            "hypergeometric union bounds for an exact universal ceiling."
        ),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=1028)
    parser.add_argument("--random-baselines", type=int, default=6)
    parser.add_argument("--candidate-samples-per-ticket", type=int, default=12)
    parser.add_argument("--max-passes", type=int, default=2)
    args = parser.parse_args()

    result = run_k235_research_comparison(
        seed=args.seed,
        random_baseline_count=args.random_baselines,
        candidate_samples_per_ticket=args.candidate_samples_per_ticket,
        max_passes=args.max_passes,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
