"""Verify the candidate-cover boundary separately from fixed-K portfolio legality."""

from __future__ import annotations

import itertools
import math
from dataclasses import replace
from typing import cast
from unittest.mock import Mock

import pytest

from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.research import covering_design_fixed_k_bridge as bridge
from lottolab.research.covering_design_tabu7 import (
    TabuSearch7Result,
    TabuSearch7RunConfig,
    run_covering_design_tabu7,
)
from lottolab.research.low_overlap_portfolio_constructor import build_low_overlap_portfolio

_CONFIG = TabuSearch7RunConfig(constructor_seed=29, search_seed=31, max_iterations=1)


@pytest.fixture(scope="module")
def real_result() -> TabuSearch7Result:
    # One real pool is shared by all K and all damaged-source cases.
    return run_covering_design_tabu7(v=49, k=6, t=2, config=_CONFIG)


def _mapped_candidates(result: TabuSearch7Result) -> tuple[tuple[int, ...], ...]:
    return tuple(
        sorted(
            {tuple(sorted(number + 1 for number in block)) for block in result.best_complete_blocks}
        )
    )


def _uncovered_pairs(tickets: tuple[tuple[int, ...], ...]) -> set[tuple[int, ...]]:
    # Independent membership oracle, not the bridge's pair-union implementation.
    blocks = [set(ticket) for ticket in tickets]
    return {
        pair
        for pair in itertools.combinations(range(1, 50), 2)
        if not any(set(pair) <= block for block in blocks)
    }


def _assert_fixed_k_portfolio(portfolio: tuple[tuple[int, ...], ...], k_ticket: int) -> None:
    assert len(portfolio) == k_ticket
    assert len(set(portfolio)) == k_ticket
    for ticket in portfolio:
        assert ticket == tuple(sorted(ticket))
        assert len(ticket) == len(set(ticket)) == 6
        assert all(type(number) is int and 1 <= number <= 49 for number in ticket)
    # Even without repeated pairs, every supported K is too small to cover 1..49.
    assert k_ticket * math.comb(6, 2) < math.comb(49, 2)
    assert _uncovered_pairs(portfolio)


def test_real_end_to_end_bridge_is_reproducible() -> None:
    assert bridge.run_covering_design_tabu7 is run_covering_design_tabu7
    assert bridge.build_low_overlap_portfolio is build_low_overlap_portfolio
    first = bridge.build_big_lotto_fixed_k_portfolio_from_tabu7_cover(20, config=_CONFIG)
    second = bridge.build_big_lotto_fixed_k_portfolio_from_tabu7_cover(20, config=_CONFIG)
    _assert_fixed_k_portfolio(first, 20)
    assert first == second  # Ticket contents AND selector order; both calls are unmocked.


@pytest.mark.parametrize("k_ticket", (2, 3, 5, 10, 20))
def test_all_k_compose_the_real_selector_with_one_real_complete_pool(
    k_ticket: int, real_result: TabuSearch7Result, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidates = _mapped_candidates(real_result)
    assert not _uncovered_pairs(candidates)
    producer = Mock(return_value=real_result)
    selector = Mock(wraps=build_low_overlap_portfolio)
    monkeypatch.setattr(bridge, "run_covering_design_tabu7", producer)
    monkeypatch.setattr(bridge, "build_low_overlap_portfolio", selector)

    portfolio = bridge.build_big_lotto_fixed_k_portfolio_from_tabu7_cover(k_ticket, config=_CONFIG)

    producer.assert_called_once_with(v=49, k=6, t=2, config=_CONFIG)
    selector.assert_called_once_with(
        candidates, k_ticket, BIG_LOTTO_RULE_CONTRACT, optional_scores=None
    )
    _assert_fixed_k_portfolio(portfolio, k_ticket)
    assert portfolio == build_low_overlap_portfolio(
        candidates, k_ticket, BIG_LOTTO_RULE_CONTRACT, optional_scores=None
    )


def test_saved_complete_pool_is_authority_and_normalization_is_deterministic(
    real_result: TabuSearch7Result, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = _mapped_candidates(real_result)
    scrambled = tuple(
        tuple(reversed(block)) for block in reversed(real_result.best_complete_blocks)
    )
    source = replace(
        real_result,
        best_complete_blocks=(*scrambled, scrambled[0], scrambled[-1]),
        final_blocks=((0, 1, 2, 3, 4, 5),),
        final_conflicts=999,
    )
    assert _uncovered_pairs(((1, 2, 3, 4, 5, 6),))
    producer = Mock(return_value=source)
    # Deliberately non-lexical order makes accidental output reordering falsifiable.
    selected = tuple(reversed(expected[:3]))
    selector = Mock(return_value=selected)
    monkeypatch.setattr(bridge, "run_covering_design_tabu7", producer)
    monkeypatch.setattr(bridge, "build_low_overlap_portfolio", selector)

    actual = bridge.build_big_lotto_fixed_k_portfolio_from_tabu7_cover(3, config=_CONFIG)

    selector.assert_called_once_with(expected, 3, BIG_LOTTO_RULE_CONTRACT, optional_scores=None)
    assert actual == selected
    _assert_fixed_k_portfolio(actual, 3)


@pytest.mark.parametrize("empty", (False, True))
def test_damaged_saved_cover_is_rejected_even_when_final_pool_is_complete(
    empty: bool, real_result: TabuSearch7Result, monkeypatch: pytest.MonkeyPatch
) -> None:
    damaged = (
        ()
        if empty
        else tuple(block for block in real_result.best_complete_blocks if not {0, 48} <= set(block))
    )
    source = replace(
        real_result, best_complete_blocks=damaged, final_blocks=real_result.best_complete_blocks
    )
    assert (1, 49) in _uncovered_pairs(_mapped_candidates(source))
    selector = Mock()
    monkeypatch.setattr(bridge, "run_covering_design_tabu7", Mock(return_value=source))
    monkeypatch.setattr(bridge, "build_low_overlap_portfolio", selector)

    with pytest.raises(ValueError, match="not a complete Big Lotto pair-cover"):
        bridge.build_big_lotto_fixed_k_portfolio_from_tabu7_cover(20, config=_CONFIG)
    selector.assert_not_called()


@pytest.mark.parametrize(
    ("bad_block", "message"),
    [
        ((0, 1, 2, 3, 4), "six numbers"),
        ((0, 1, 2, 3, 4, 5, 6), "six numbers"),
        ((0, 1, 2, 3, 4, 4), "duplicate"),
        ((-1, 1, 2, 3, 4, 5), "outside"),
        ((0, 1, 2, 3, 4, 49), "outside"),
        ((False, 1, 2, 3, 4, 5), "non-integer"),
        ((0.0, 1, 2, 3, 4, 5), "non-integer"),
        (("0", 1, 2, 3, 4, 5), "non-integer"),
    ],
)
def test_illegal_candidate_is_rejected_even_if_other_candidates_cover_all_pairs(
    bad_block: tuple[object, ...],
    message: str,
    real_result: TabuSearch7Result,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = replace(
        real_result,
        best_complete_blocks=(*real_result.best_complete_blocks, cast(tuple[int, ...], bad_block)),
    )
    selector = Mock()
    monkeypatch.setattr(bridge, "run_covering_design_tabu7", Mock(return_value=source))
    monkeypatch.setattr(bridge, "build_low_overlap_portfolio", selector)
    with pytest.raises(ValueError, match=message):
        bridge.build_big_lotto_fixed_k_portfolio_from_tabu7_cover(2, config=_CONFIG)
    selector.assert_not_called()


@pytest.mark.parametrize("unsupported", (-1, 0, 1, 4, 6, 15, 21, 100, True, 2.0, "2", None))
def test_unsupported_k_fails_before_producer(
    unsupported: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    producer = Mock()
    monkeypatch.setattr(bridge, "run_covering_design_tabu7", producer)
    with pytest.raises(ValueError, match="k_ticket"):
        bridge.build_big_lotto_fixed_k_portfolio_from_tabu7_cover(
            cast(int, unsupported), config=_CONFIG
        )
    producer.assert_not_called()


@pytest.mark.parametrize("failing_endpoint", ("producer", "selector"))
def test_endpoint_errors_propagate_unchanged(
    failing_endpoint: str, real_result: TabuSearch7Result, monkeypatch: pytest.MonkeyPatch
) -> None:
    error = RuntimeError("upstream sentinel failure")
    producer = Mock(return_value=real_result)
    selector = Mock(wraps=build_low_overlap_portfolio)
    if failing_endpoint == "producer":
        producer.side_effect = error
    else:
        selector.side_effect = error
    monkeypatch.setattr(bridge, "run_covering_design_tabu7", producer)
    monkeypatch.setattr(bridge, "build_low_overlap_portfolio", selector)
    with pytest.raises(RuntimeError) as caught:
        bridge.build_big_lotto_fixed_k_portfolio_from_tabu7_cover(2, config=_CONFIG)
    assert caught.value is error


def test_public_claim_boundary_applies_complete_pair_cover_only_to_candidates() -> None:
    documentation = bridge.__doc__ or ""
    assert "CANDIDATE_POOL_COMPLETE_PAIR_COVER: YES" in documentation
    assert "SELECTED_FIXED_K_PORTFOLIO_COMPLETE_PAIR_COVER: NOT_CLAIMED" in documentation
    assert "fixed-K portfolio is not a complete covering design" in documentation
