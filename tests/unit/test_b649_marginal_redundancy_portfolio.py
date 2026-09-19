"""Focused tests for the frozen B649_MARGINAL_REDUNDANCY_PORTFOLIO_V1 candidate."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from lottolab.application.b649_operational_portfolio_selector import (
    StrategyCandidate,
    Ticket,
    build_portfolio,
)
from lottolab.research.b649_marginal_redundancy_portfolio import (
    CANDIDATE_NAME,
    CANDIDATE_VERSION,
    OUTCOME_FIELDS_USED,
    PRE_DRAW_FEATURES_USED,
    SUPPORTED_K,
    build_marginal_redundancy_portfolio,
    candidate_identity,
    incumbent_base_order,
)
from lottolab.research.biglotto_multi_ticket_constructors_r1 import (
    construct_b649_candidate_set_low_overlap_v1,
)

DISJOINT_FIVE: tuple[Ticket, ...] = (
    (1, 2, 3, 4, 11, 12),
    (5, 6, 7, 8, 9, 10),
    (13, 14, 15, 16, 17, 18),
    (20, 21, 22, 23, 24, 25),
    (30, 31, 32, 33, 34, 35),
)
# Same five incumbent ranks, but rank 0 now shares five numbers with rank 1.
OVERLAPPING_FIVE: tuple[Ticket, ...] = (
    (1, 5, 6, 7, 8, 9),
    (5, 6, 7, 8, 9, 10),
    (13, 14, 15, 16, 17, 18),
    (20, 21, 22, 23, 24, 25),
    (30, 31, 32, 33, 34, 35),
)


def one_stream_each(tickets: tuple[Ticket, ...]) -> list[StrategyCandidate]:
    """One distinct stream per ticket, so every ticket has support count 1."""
    return [StrategyCandidate(f"s{i}", [ticket]) for i, ticket in enumerate(tickets)]


def twenty_ticket_pool() -> list[StrategyCandidate]:
    """Twenty distinct tickets spread over eleven streams, K20-eligible."""
    tickets: list[Ticket] = [(1 + i, 2 + i, 11 + i, 12 + i, 22 + i, 29 + i) for i in range(20)]
    return [StrategyCandidate(f"stream{i % 11}", [ticket]) for i, ticket in enumerate(tickets)]


def test_base_order_is_the_unmodified_incumbent_order() -> None:
    candidates = twenty_ticket_pool()
    base = incumbent_base_order(candidates)
    buckets = build_portfolio(candidates, {}, bucket_sizes=(5, 10, 20))
    assert len(base) == 20
    for k in (5, 10, 20):
        assert list(base[:k]) == buckets[k]


def test_budgets_are_nested_prefixes_of_one_total_order() -> None:
    portfolio = build_marginal_redundancy_portfolio(twenty_ticket_pool())
    assert portfolio.tickets_by_k[20][:5] == portfolio.tickets_by_k[5]
    assert portfolio.tickets_by_k[20][:10] == portfolio.tickets_by_k[10]
    assert portfolio.ranked_order == portfolio.tickets_by_k[20]


def test_matches_the_canonical_constructor_called_directly() -> None:
    candidates = twenty_ticket_pool()
    base = incumbent_base_order(candidates)
    portfolio = build_marginal_redundancy_portfolio(candidates)
    for k in SUPPORTED_K:
        assert portfolio.tickets_by_k[k] == construct_b649_candidate_set_low_overlap_v1(base, k)


def test_determinism_same_input_same_total_order_and_selections() -> None:
    candidates = twenty_ticket_pool()
    first = build_marginal_redundancy_portfolio(candidates)
    second = build_marginal_redundancy_portfolio(candidates)
    assert first.base_order == second.base_order
    assert first.ranked_order == second.ranked_order
    for k in SUPPORTED_K:
        assert first.tickets_by_k[k] == second.tickets_by_k[k]


def test_determinism_is_invariant_to_stream_input_order() -> None:
    candidates = twenty_ticket_pool()
    forward = build_marginal_redundancy_portfolio(candidates)
    reversed_streams = build_marginal_redundancy_portfolio(list(reversed(candidates)))
    assert reversed_streams.base_order == forward.base_order
    assert reversed_streams.ranked_order == forward.ranked_order


def test_top_ranked_ticket_is_the_incumbent_top_ranked_ticket() -> None:
    """With an empty selected prefix every overlap is zero, so rank decides."""
    portfolio = build_marginal_redundancy_portfolio(twenty_ticket_pool())
    assert portfolio.ranked_order[0] == portfolio.base_order[0]


def test_mutually_disjoint_pool_reproduces_the_incumbent_order() -> None:
    """Redundancy is inert when no two tickets share a number, so rank alone decides."""
    candidates = one_stream_each(
        tuple(tuple(range(1 + 6 * i, 7 + 6 * i)) for i in range(8))  # type: ignore[misc]
    )
    portfolio = build_marginal_redundancy_portfolio(candidates, budgets=(5,))
    assert portfolio.tickets_by_k[5] == portfolio.base_order[:5]


def test_redundancy_demotes_a_near_duplicate_the_incumbent_promotes() -> None:
    candidates = one_stream_each(OVERLAPPING_FIVE)
    incumbent = build_portfolio(candidates, {}, bucket_sizes=(5,))[5]
    portfolio = build_marginal_redundancy_portfolio(candidates, budgets=(5,))
    near_duplicate = (5, 6, 7, 8, 9, 10)
    assert incumbent.index(near_duplicate) == 1
    assert portfolio.tickets_by_k[5].index(near_duplicate) == 4


def test_not_a_function_of_the_incumbent_pointwise_key() -> None:
    """Decisive falsification of "support-count equivalent".

    The same ticket keeps support count 1, incumbent rank 1 and pool size 5 in
    both pools, yet its candidate rank moves from 1 to 4. No function of the
    incumbent's per-ticket key ``(-support, -quality, ticket)`` can do that,
    because that key is identical in both pools.
    """
    ticket = (5, 6, 7, 8, 9, 10)
    ranks: list[int] = []
    for pool_tickets in (DISJOINT_FIVE, OVERLAPPING_FIVE):
        candidates = one_stream_each(pool_tickets)
        base = incumbent_base_order(candidates)
        assert base.index(ticket) == 1
        assert build_portfolio(candidates, {}, bucket_sizes=(5,))[5].index(ticket) == 1
        portfolio = build_marginal_redundancy_portfolio(candidates, budgets=(5,))
        ranks.append(portfolio.tickets_by_k[5].index(ticket))
    assert ranks == [1, 4]


def test_rejects_unsupported_budget() -> None:
    with pytest.raises(ValueError, match="UNSUPPORTED_BUDGET"):
        build_marginal_redundancy_portfolio(twenty_ticket_pool(), budgets=(3,))


def test_rejects_pool_smaller_than_the_largest_budget() -> None:
    candidates = one_stream_each(DISJOINT_FIVE)
    with pytest.raises(ValueError, match="POOL_TOO_SMALL"):
        build_marginal_redundancy_portfolio(candidates, budgets=(5, 10))


def test_rejects_empty_pool() -> None:
    with pytest.raises(ValueError, match="EMPTY_CANDIDATE_POOL"):
        incumbent_base_order([])


def test_candidate_identity_is_the_frozen_definition() -> None:
    identity = candidate_identity()
    assert identity["CANDIDATE_NAME"] == CANDIDATE_NAME == "B649_MARGINAL_REDUNDANCY_PORTFOLIO_V1"
    assert identity["CANDIDATE_VERSION"] == CANDIDATE_VERSION == "1.0.0"
    assert identity["SUPPORTED_K"] == [5, 10, 20]
    assert identity["OUTCOME_FIELDS_USED"] == "NONE"
    assert identity["PRE_DRAW_FEATURES_USED"] == list(PRE_DRAW_FEATURES_USED)
    assert PRE_DRAW_FEATURES_USED[0].startswith("MAX_OVERLAP")


def test_candidate_module_consumes_no_outcome_authority() -> None:
    """Static import guard: the ranking module reaches no outcome/prize surface."""
    source = Path("src/lottolab/research/b649_marginal_redundancy_portfolio.py").read_text()
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert imported == {
        "__future__",
        "collections.abc",
        "dataclasses",
        "itertools",
        "typing",
        "lottolab.application.b649_operational_portfolio_selector",
        "lottolab.research.biglotto_multi_ticket_constructors_r1",
    }
    # Identifiers only: prose in the module docstring must not trip this guard.
    identifiers: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)
        elif isinstance(node, (ast.ImportFrom, ast.Import)):
            identifiers.update(alias.name for alias in node.names)
    forbidden = ("prize", "hit", "winning", "special", "outcome", "evaluate", "draw_result")
    # The module's own negative declaration is the single allowed match, and its
    # value is asserted here so the exemption cannot hide a real consumer.
    assert OUTCOME_FIELDS_USED == "NONE"
    flagged = [
        name for name in sorted(identifiers) if any(bad in name.lower() for bad in forbidden)
    ]
    assert flagged == ["OUTCOME_FIELDS_USED"]


SUPPORT_TWO_POOL: tuple[StrategyCandidate, ...] = (
    StrategyCandidate("a", [(44, 45, 46, 47, 48, 49)]),
    StrategyCandidate("b", [(44, 45, 46, 47, 48, 49)]),
    StrategyCandidate("c", [(1, 2, 3, 4, 5, 6)]),
    StrategyCandidate("d", [(1, 2, 3, 4, 5, 7)]),
    StrategyCandidate("e", [(10, 11, 12, 13, 14, 15)]),
    StrategyCandidate("f", [(20, 21, 22, 23, 24, 25)]),
)


def twenty_two_ticket_pool() -> list[StrategyCandidate]:
    """Twenty near-duplicates that sort first, then two disjoint tail tickets."""
    tickets: list[Ticket] = [(1, 2, 3, 4, 5, 6 + i) for i in range(20)]
    tickets.append((38, 39, 40, 41, 42, 43))
    tickets.append((44, 45, 46, 47, 48, 49))
    return [StrategyCandidate(f"stream{i % 11}", [t]) for i, t in enumerate(tickets)]


def test_base_order_is_the_incumbent_not_plain_lexicographic_order() -> None:
    """Cross-stream support still outranks the ticket, so the tail ticket leads."""
    candidates = list(SUPPORT_TWO_POOL)
    supported_twice = (44, 45, 46, 47, 48, 49)
    base = incumbent_base_order(candidates)
    assert base[0] == supported_twice
    assert base != tuple(sorted(base))
    portfolio = build_marginal_redundancy_portfolio(candidates, budgets=(5,))
    assert portfolio.tickets_by_k[5][0] == supported_twice


def test_selection_reaches_pool_tickets_ranked_below_the_largest_budget() -> None:
    """The whole distinct pool is rankable, not just the incumbent's top K20."""
    candidates = twenty_two_ticket_pool()
    base = incumbent_base_order(candidates)
    assert len(base) == 22
    beyond_k20 = base[21]
    portfolio = build_marginal_redundancy_portfolio(candidates)
    assert beyond_k20 not in build_portfolio(candidates, {}, bucket_sizes=(20,))[20]
    assert beyond_k20 in portfolio.tickets_by_k[5]
