"""Descriptive rank-stability diagnostics over B649 portfolio ranking candidates.

Read-only diagnostics over already-produced ``StrategyCandidate`` streams and
externally supplied per-budget / per-window rankings. Never retrains, replays,
or inspects outcome data; a missing input is reported unavailable rather than
synthesized from other inputs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from statistics import median

from lottolab.application.b649_operational_portfolio_selector import (
    StrategyCandidate,
    Ticket,
    build_portfolio,
)

DEFAULT_BUDGETS: tuple[int, ...] = (2, 3, 5, 10, 20)
DEFAULT_WINDOWS: tuple[str, ...] = ("FULL", "RECENT_750", "RECENT_300")


def normalize_ticket(raw: Sequence[int]) -> Ticket:
    ticket = tuple(sorted(raw))
    if len(ticket) != 6 or len(set(ticket)) != 6:
        raise ValueError(f"invalid ticket: {raw}")
    return ticket


def _supporters(candidates: Sequence[StrategyCandidate]) -> dict[Ticket, set[str]]:
    supporting: dict[Ticket, set[str]] = {}
    for candidate in candidates:
        for raw in candidate.tickets:
            ticket = normalize_ticket(raw)
            supporting.setdefault(ticket, set()).add(candidate.strategy_id)
    return supporting


def _feasible_buckets(
    candidates: Sequence[StrategyCandidate],
    quality_by_strategy: Mapping[str, float],
    budgets: Sequence[int],
) -> dict[int, list[Ticket]]:
    distinct_count = len(_supporters(candidates))
    feasible = [budget for budget in budgets if budget <= distinct_count]
    if not feasible:
        return {}
    return build_portfolio(candidates, quality_by_strategy, bucket_sizes=feasible)


# ---------------------------------------------------------------------------
# A. Stream support matrix
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StreamSupportRow:
    ticket: Ticket
    supporting_streams: tuple[str, ...]
    stream_support_count: int
    ticket_occurrence_count: int


@dataclass(frozen=True)
class NumberFrequencyRow:
    number: int
    ticket_count: int
    occurrence_count: int


@dataclass(frozen=True)
class StreamSupportMatrix:
    ticket_rows: tuple[StreamSupportRow, ...]
    number_rows: tuple[NumberFrequencyRow, ...]


def compute_stream_support_matrix(
    candidates: Sequence[StrategyCandidate],
) -> StreamSupportMatrix:
    """Deterministic per-ticket stream support plus per-number frequency.

    A ticket repeated within one stream's own ``tickets`` list contributes
    once to that ticket's distinct stream support, but each repeat still
    counts toward ``ticket_occurrence_count``.
    """
    supporting = _supporters(candidates)
    occurrences: dict[Ticket, int] = {}
    number_tickets: dict[int, set[Ticket]] = {}
    number_occurrences: dict[int, int] = {}

    for candidate in candidates:
        for raw in candidate.tickets:
            ticket = normalize_ticket(raw)
            occurrences[ticket] = occurrences.get(ticket, 0) + 1
            for number in ticket:
                number_tickets.setdefault(number, set()).add(ticket)
                number_occurrences[number] = number_occurrences.get(number, 0) + 1

    ticket_rows = tuple(
        StreamSupportRow(
            ticket=ticket,
            supporting_streams=tuple(sorted(supporting[ticket])),
            stream_support_count=len(supporting[ticket]),
            ticket_occurrence_count=occurrences[ticket],
        )
        for ticket in sorted(supporting)
    )
    number_rows = tuple(
        NumberFrequencyRow(
            number=number,
            ticket_count=len(number_tickets[number]),
            occurrence_count=number_occurrences[number],
        )
        for number in sorted(number_tickets)
    )
    return StreamSupportMatrix(ticket_rows=ticket_rows, number_rows=number_rows)


# ---------------------------------------------------------------------------
# B. Cross-budget persistence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BudgetPersistenceRow:
    ticket: Ticket
    rank_by_budget: tuple[tuple[int, int | None], ...]
    survival_count: int
    min_rank: int | None
    max_rank: int | None
    median_rank: float | None
    entry_budgets: tuple[int, ...]
    exit_budgets: tuple[int, ...]


@dataclass(frozen=True)
class CrossBudgetPersistenceReport:
    available_budgets: tuple[int, ...]
    unavailable_budgets: tuple[int, ...]
    ticket_rows: tuple[BudgetPersistenceRow, ...]


def compute_cross_budget_persistence(
    rankings_by_budget: Mapping[int, Sequence[Ticket] | None],
    budgets: Sequence[int] = DEFAULT_BUDGETS,
) -> CrossBudgetPersistenceReport:
    """Persistence across independently supplied per-budget rankings.

    Each budget's ranking must come from its own independently produced
    input; this never slices one master ranking to manufacture nesting. A
    budget absent from ``rankings_by_budget`` or mapped to ``None`` is
    reported unavailable, never synthesized.
    """
    available = tuple(b for b in budgets if rankings_by_budget.get(b) is not None)
    unavailable = tuple(b for b in budgets if rankings_by_budget.get(b) is None)

    rank_by_ticket: dict[Ticket, dict[int, int]] = {}
    for budget in available:
        ranking = rankings_by_budget[budget]
        if ranking is None:
            continue
        for index, raw in enumerate(ranking):
            ticket = normalize_ticket(raw)
            rank_by_ticket.setdefault(ticket, {})[budget] = index + 1

    rows: list[BudgetPersistenceRow] = []
    for ticket in sorted(rank_by_ticket):
        per_budget = rank_by_ticket[ticket]
        ranks = [per_budget[b] for b in available if b in per_budget]
        entries: list[int] = []
        exits: list[int] = []
        previously_present: bool | None = None
        for budget in available:
            present = budget in per_budget
            if previously_present is not None:
                if present and not previously_present:
                    entries.append(budget)
                elif previously_present and not present:
                    exits.append(budget)
            previously_present = present
        rows.append(
            BudgetPersistenceRow(
                ticket=ticket,
                rank_by_budget=tuple((b, per_budget.get(b)) for b in available),
                survival_count=len(ranks),
                min_rank=min(ranks) if ranks else None,
                max_rank=max(ranks) if ranks else None,
                median_rank=median(ranks) if ranks else None,
                entry_budgets=tuple(entries),
                exit_budgets=tuple(exits),
            )
        )

    return CrossBudgetPersistenceReport(
        available_budgets=available,
        unavailable_budgets=unavailable,
        ticket_rows=tuple(rows),
    )


# ---------------------------------------------------------------------------
# C. Leave-one-stream-out stability
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LooBudgetResult:
    budget: int
    available: bool
    top_k_retained: tuple[Ticket, ...] | None
    retention_count: int | None
    additions: tuple[Ticket, ...] | None
    removals: tuple[Ticket, ...] | None
    flips: tuple[tuple[Ticket, Ticket], ...] | None
    comparable_rank_deltas: tuple[tuple[Ticket, int], ...] | None
    worst_rank_delta: int | None


@dataclass(frozen=True)
class LooOmissionResult:
    omitted_stream_id: str
    budgets: tuple[LooBudgetResult, ...]


@dataclass(frozen=True)
class LooStabilityReport:
    baseline_feasible_budgets: tuple[int, ...]
    omissions: tuple[LooOmissionResult, ...]
    worst_perturbation_budget: int | None
    worst_perturbation_stream: str | None
    worst_perturbation_rank_delta: int | None


def compute_loo_stability(
    candidates: Sequence[StrategyCandidate],
    quality_by_strategy: Mapping[str, float] | None = None,
    budgets: Sequence[int] = DEFAULT_BUDGETS,
) -> LooStabilityReport:
    """Leave-one-stream-out perturbation, reusing canonical ``build_portfolio``.

    For each stream, recompute the ranking with that stream removed and
    compare to the full-stream baseline at each requested budget. A budget
    infeasible for the baseline or for a given omission (too few distinct
    tickets) is reported unavailable for that (stream, budget) pair rather
    than raised or approximated. Never retrains, replays, or inspects
    outcomes.
    """
    quality = quality_by_strategy or {}
    baseline_buckets = _feasible_buckets(candidates, quality, budgets)
    baseline_feasible = tuple(sorted(baseline_buckets))

    stream_ids = tuple(sorted({c.strategy_id for c in candidates}))
    omissions: list[LooOmissionResult] = []
    worst_budget: int | None = None
    worst_stream: str | None = None
    worst_delta: int | None = None

    for stream_id in stream_ids:
        reduced = [c for c in candidates if c.strategy_id != stream_id]
        reduced_buckets = _feasible_buckets(reduced, quality, budgets)

        budget_results: list[LooBudgetResult] = []
        for budget in budgets:
            if budget not in baseline_buckets or budget not in reduced_buckets:
                budget_results.append(
                    LooBudgetResult(
                        budget=budget,
                        available=False,
                        top_k_retained=None,
                        retention_count=None,
                        additions=None,
                        removals=None,
                        flips=None,
                        comparable_rank_deltas=None,
                        worst_rank_delta=None,
                    )
                )
                continue

            baseline_ranking = baseline_buckets[budget]
            omission_ranking = reduced_buckets[budget]
            baseline_rank = {t: i + 1 for i, t in enumerate(baseline_ranking)}
            omission_rank = {t: i + 1 for i, t in enumerate(omission_ranking)}

            baseline_set = set(baseline_ranking)
            omission_set = set(omission_ranking)
            common = sorted(baseline_set & omission_set)
            additions = tuple(sorted(omission_set - baseline_set))
            removals = tuple(sorted(baseline_set - omission_set))

            deltas = tuple((t, omission_rank[t] - baseline_rank[t]) for t in common)
            worst: int | None = max((abs(d) for _, d in deltas), default=None)

            flips: list[tuple[Ticket, Ticket]] = []
            for i, a in enumerate(common):
                for b in common[i + 1 :]:
                    baseline_order = baseline_rank[a] - baseline_rank[b]
                    omission_order = omission_rank[a] - omission_rank[b]
                    if (baseline_order < 0) != (omission_order < 0):
                        flips.append((a, b))

            budget_results.append(
                LooBudgetResult(
                    budget=budget,
                    available=True,
                    top_k_retained=tuple(common),
                    retention_count=len(common),
                    additions=additions,
                    removals=removals,
                    flips=tuple(flips),
                    comparable_rank_deltas=deltas,
                    worst_rank_delta=worst,
                )
            )
            if worst is not None and (worst_delta is None or worst > worst_delta):
                worst_delta = worst
                worst_budget = budget
                worst_stream = stream_id

        omissions.append(
            LooOmissionResult(omitted_stream_id=stream_id, budgets=tuple(budget_results))
        )

    return LooStabilityReport(
        baseline_feasible_budgets=baseline_feasible,
        omissions=tuple(omissions),
        worst_perturbation_budget=worst_budget,
        worst_perturbation_stream=worst_stream,
        worst_perturbation_rank_delta=worst_delta,
    )


# ---------------------------------------------------------------------------
# D. Window stability
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WindowPersistenceRow:
    ticket: Ticket
    rank_by_window: tuple[tuple[str, int | None], ...]
    presence_count: int
    min_rank: int | None
    max_rank: int | None
    median_rank: float | None
    rank_range: int | None
    entry_windows: tuple[str, ...]
    exit_windows: tuple[str, ...]


@dataclass(frozen=True)
class WindowStabilityReport:
    available_windows: tuple[str, ...]
    unavailable_windows: tuple[str, ...]
    ticket_rows: tuple[WindowPersistenceRow, ...]


def compute_window_stability(
    rankings_by_window: Mapping[str, Sequence[Ticket] | None],
    windows: Sequence[str] = DEFAULT_WINDOWS,
) -> WindowStabilityReport:
    """Rank persistence across supplied window rankings only.

    Consumes exactly the window rankings/evidence supplied by the caller;
    never constructs outcome windows. A window absent from
    ``rankings_by_window`` or mapped to ``None`` is reported unavailable.
    """
    available = tuple(w for w in windows if rankings_by_window.get(w) is not None)
    unavailable = tuple(w for w in windows if rankings_by_window.get(w) is None)

    rank_by_ticket: dict[Ticket, dict[str, int]] = {}
    for window in available:
        ranking = rankings_by_window[window]
        if ranking is None:
            continue
        for index, raw in enumerate(ranking):
            ticket = normalize_ticket(raw)
            rank_by_ticket.setdefault(ticket, {})[window] = index + 1

    rows: list[WindowPersistenceRow] = []
    for ticket in sorted(rank_by_ticket):
        per_window = rank_by_ticket[ticket]
        ranks = [per_window[w] for w in available if w in per_window]
        entries: list[str] = []
        exits: list[str] = []
        previously_present: bool | None = None
        for window in available:
            present = window in per_window
            if previously_present is not None:
                if present and not previously_present:
                    entries.append(window)
                elif previously_present and not present:
                    exits.append(window)
            previously_present = present
        rows.append(
            WindowPersistenceRow(
                ticket=ticket,
                rank_by_window=tuple((w, per_window.get(w)) for w in available),
                presence_count=len(ranks),
                min_rank=min(ranks) if ranks else None,
                max_rank=max(ranks) if ranks else None,
                median_rank=median(ranks) if ranks else None,
                rank_range=(max(ranks) - min(ranks)) if ranks else None,
                entry_windows=tuple(entries),
                exit_windows=tuple(exits),
            )
        )

    return WindowStabilityReport(
        available_windows=available,
        unavailable_windows=unavailable,
        ticket_rows=tuple(rows),
    )


# ---------------------------------------------------------------------------
# E. Selection boundary
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SelectionBoundaryPair:
    lower_budget: int
    upper_budget: int
    available: bool
    selected_boundary_ticket: Ticket | None
    first_excluded_ticket: Ticket | None
    support_difference: int | None
    quality_sum_difference: float | None
    exact_tie: bool | None
    same_support_band: bool | None


@dataclass(frozen=True)
class SelectionBoundaryReport:
    pairs: tuple[SelectionBoundaryPair, ...]


def compute_selection_boundary(
    candidates: Sequence[StrategyCandidate],
    quality_by_strategy: Mapping[str, float] | None = None,
    budgets: Sequence[int] = DEFAULT_BUDGETS,
) -> SelectionBoundaryReport:
    """Selected-vs-first-excluded boundary for each adjacent budget pair.

    ``exact_tie``/``same_support_band`` are always computed from whatever
    support and quality information is available (quality contributes zero
    when unsupplied, matching ``build_portfolio``'s own tie-break); only the
    reported ``quality_sum_difference`` value is gated on quality actually
    being supplied. No near-tie threshold is invented.
    """
    supporting = _supporters(candidates)
    quality = quality_by_strategy or {}
    quality_supplied = quality_by_strategy is not None
    ordered_budgets = sorted(set(budgets))
    buckets = _feasible_buckets(candidates, quality, ordered_budgets)

    def support_count(ticket: Ticket) -> int:
        return len(supporting[ticket])

    def quality_sum(ticket: Ticket) -> float:
        return sum(quality.get(s, 0.0) for s in supporting[ticket])

    pairs: list[SelectionBoundaryPair] = []
    for lower, upper in pairwise(ordered_budgets):
        if upper not in buckets:
            pairs.append(
                SelectionBoundaryPair(
                    lower_budget=lower,
                    upper_budget=upper,
                    available=False,
                    selected_boundary_ticket=None,
                    first_excluded_ticket=None,
                    support_difference=None,
                    quality_sum_difference=None,
                    exact_tie=None,
                    same_support_band=None,
                )
            )
            continue

        ranking = buckets[upper]
        boundary = ranking[lower - 1]
        excluded = ranking[lower]
        support_diff = support_count(boundary) - support_count(excluded)
        same_band = support_diff == 0
        quality_diff = quality_sum(boundary) - quality_sum(excluded)
        exact_tie = same_band and quality_diff == 0

        pairs.append(
            SelectionBoundaryPair(
                lower_budget=lower,
                upper_budget=upper,
                available=True,
                selected_boundary_ticket=boundary,
                first_excluded_ticket=excluded,
                support_difference=support_diff,
                quality_sum_difference=quality_diff if quality_supplied else None,
                exact_tie=exact_tie,
                same_support_band=same_band,
            )
        )

    return SelectionBoundaryReport(pairs=tuple(pairs))
