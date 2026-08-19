"""Exact parity and runtime tests for the B649 Apriori base method intake."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from typing import Final

import pytest

from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GeneratePortfolioStatus,
    build_production_generate_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, ResponseShape
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_apriori import (
    BigLottoAprioriStrategyAdapter,
    _apriori_portfolio,
    _seed_integer,
    _target_after_causal_cutoff,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID: Final = "legacy_biglotto__backtest_apriori__2abb53765703"


def _rows(tickets: tuple[tuple[int, ...], ...]) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(
            draw=str(index + 1),
            date=f"2024-01-{index + 1:02d}",
            numbers=ticket,
        )
        for index, ticket in enumerate(tickets)
    )


@dataclass(frozen=True, slots=True)
class _OracleRule:
    antecedent: tuple[int, ...]
    consequent: int
    confidence: float


def _donor_apriori_portfolio(
    history: tuple[CausalDrawRow, ...],
    *,
    target_draw_number: str | None = None,
) -> tuple[tuple[int, ...], ...]:
    """Independent oracle transcribed directly from tools/backtest_apriori.py."""
    target = (
        target_draw_number
        if target_draw_number is not None
        else _target_after_causal_cutoff(history)
    )
    seed = _seed_integer(target)
    rng = random.Random()
    rng.seed(seed, version=2)

    source_history: list[list[int]] = [list(row.numbers) for row in history[-150:]]

    # 1. Mine Frequent Itemsets
    counts: defaultdict[tuple[int, ...], int] = defaultdict(int)
    for draw_numbers in source_history:
        nums = sorted(draw_numbers)
        for n in nums:
            counts[(n,)] += 1
        for pair in combinations(nums, 2):
            counts[pair] += 1
        for trio in combinations(nums, 3):
            counts[trio] += 1
    frequent = {k: v for k, v in counts.items() if v >= 3}

    # 2. Generate Rules
    rules: list[_OracleRule] = []
    for itemset, support_union in frequent.items():
        if len(itemset) < 2:
            continue
        for consequent_tuple in combinations(itemset, 1):
            consequent = consequent_tuple[0]
            antecedent = tuple(sorted(set(itemset) - {consequent}))
            if antecedent in frequent:
                support_antecedent = frequent[antecedent]
                confidence = support_union / support_antecedent
                if confidence >= 0.4:
                    rules.append(
                        _OracleRule(
                            antecedent=antecedent,
                            consequent=consequent,
                            confidence=confidence,
                        )
                    )
    rules.sort(key=lambda rule: rule.confidence, reverse=True)

    # 3. Build bets for num_bets in (1, 2, 3, 7)
    all_bets: list[tuple[int, ...]] = []
    for num_bets in (1, 2, 3, 7):
        bets: list[list[int]] = []
        used_rules: set[tuple[int, ...]] = set()

        for i in range(num_bets):
            target_rule: _OracleRule | None = None
            for rule in rules:
                if rule.antecedent not in used_rules:
                    target_rule = rule
                    used_rules.add(rule.antecedent)
                    break

            if target_rule is None:
                remaining = list(range(1, 50))
                bets.append(sorted(rng.sample(remaining, 6)))
                continue

            core: list[int] = [*target_rule.antecedent, target_rule.consequent]
            current_nums: list[int] = sorted(set(core))

            while len(current_nums) < 6:
                last_num = current_nums[-1]

                candidates = [
                    rule
                    for rule in rules
                    if rule.consequent not in current_nums
                    and (
                        rule.antecedent == (last_num,)
                        or (len(rule.antecedent) == 1 and rule.antecedent[0] in current_nums)
                    )
                ]

                if candidates:
                    candidates.sort(key=lambda rule: rule.confidence, reverse=True)
                    best_next = candidates[0].consequent
                else:
                    remaining_nums = [n for n in range(1, 50) if n not in current_nums]
                    if not remaining_nums:
                        break
                    best_next = remaining_nums[i % len(remaining_nums)]

                current_nums.append(best_next)
                current_nums = sorted(set(current_nums))

            bets.append(sorted(current_nums[:6]))
        all_bets.extend(tuple(sorted(b)) for b in bets)

    return tuple(all_bets)


def _patterned_history(length: int) -> tuple[CausalDrawRow, ...]:
    """Generate history with recurring sub-patterns to produce frequent rules."""
    patterns = (
        (1, 2, 3, 10, 20, 30),
        (1, 2, 4, 11, 21, 31),
        (1, 2, 3, 12, 22, 32),
        (5, 6, 7, 13, 23, 33),
        (5, 6, 8, 14, 24, 34),
        (5, 6, 7, 15, 25, 35),
    )
    return _rows(tuple(patterns[i % len(patterns)] for i in range(length)))


def test_exact_donor_parity_for_minimum_history() -> None:
    """Length 1 history: no frequent rules can reach min_support=3, exercises fallback branch."""
    adapter = BigLottoAprioriStrategyAdapter()
    history = _rows(((1, 2, 3, 4, 5, 6),))

    result = adapter.get_bets(history, LotteryType.BIG_LOTTO)
    oracle_result = _donor_apriori_portfolio(history)

    assert len(result) == 13
    assert result == oracle_result
    assert _apriori_portfolio(history) == oracle_result


def test_exact_donor_parity_for_rule_generating_history() -> None:
    """Length 30 history with structured patterns: generates frequent itemsets and rules."""
    adapter = BigLottoAprioriStrategyAdapter()
    history = _patterned_history(30)

    result = adapter.get_bets(history, LotteryType.BIG_LOTTO)
    oracle_result = _donor_apriori_portfolio(history)

    assert len(result) == 13
    assert result == oracle_result
    assert _apriori_portfolio(history) == oracle_result


def test_exact_donor_parity_and_150_draw_window_truncation() -> None:
    """History of 200 draws: only recent 150 draws should affect prediction."""
    adapter = BigLottoAprioriStrategyAdapter()
    full_history = _patterned_history(200)
    recent_150 = full_history[-150:]

    result_full = adapter.get_bets(full_history, LotteryType.BIG_LOTTO)
    oracle_full = _donor_apriori_portfolio(full_history)

    assert len(result_full) == 13
    assert result_full == oracle_full

    # Seed depends on the last draw ID; with same cutoff draw, 150-slice gives identical rules
    assert _apriori_portfolio(
        full_history, target_draw_number="cutoff_target"
    ) == _apriori_portfolio(recent_150, target_draw_number="cutoff_target")


def test_native_output_shape_legal_tickets_and_invariants() -> None:
    adapter = BigLottoAprioriStrategyAdapter()
    history = _patterned_history(50)
    executions = adapter.get_bets_with_emission(history, LotteryType.BIG_LOTTO)

    assert len(executions) == 13
    for execution in executions:
        ticket = execution.legal_main_numbers
        assert len(ticket) == 6
        assert len(set(ticket)) == 6
        assert all(1 <= num <= 49 for num in ticket)
        assert ticket == tuple(sorted(ticket))
        assert execution.special_number is None

    # Error handling
    with pytest.raises(InsufficientHistory):
        adapter.get_bets((), LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_bets(history, LotteryType.POWER_LOTTO)


def test_determinism_and_process_stability() -> None:
    adapter = BigLottoAprioriStrategyAdapter()
    history = _patterned_history(40)

    first_run = adapter.get_bets(history, LotteryType.BIG_LOTTO)
    for _ in range(5):
        assert adapter.get_bets(history, LotteryType.BIG_LOTTO) == first_run


def test_causal_history_boundary() -> None:
    history = _patterned_history(60)
    cutoff_target = _target_after_causal_cutoff(history)
    draw_ids = {row.draw for row in history}

    assert cutoff_target not in draw_ids
    assert int(history[-1].draw) < int(history[-1].draw) + 1


def test_catalog_registry_and_production_portfolio_path_are_reachable() -> None:
    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)

    assert (
        descriptor.strategy_id,
        descriptor.strategy_name,
        descriptor.version,
        descriptor.lottery_types,
        descriptor.lifecycle_status,
        descriptor.executable,
        descriptor.min_history,
        descriptor.response_shape,
        descriptor.native_ticket_count,
    ) == (
        BigLottoAprioriStrategyAdapter.strategy_id,
        BigLottoAprioriStrategyAdapter.strategy_name,
        BigLottoAprioriStrategyAdapter.strategy_version,
        (LotteryType.BIG_LOTTO,),
        LifecycleStatus.ONLINE,
        True,
        BigLottoAprioriStrategyAdapter.min_history,
        ResponseShape.PORTFOLIO,
        13,
    )
    assert ExecutableRegistry(catalog).load_adapter(STRATEGY_ID) is (BigLottoAprioriStrategyAdapter)
    assert "legacy_source:tools/backtest_apriori.py" in descriptor.provenance
    assert "current_significance:NOT_ESTABLISHED" in descriptor.provenance
    assert "predictive_advantage_claimed:NO" in descriptor.provenance

    request = GenerateOneBetInput(
        strategy_id=STRATEGY_ID,
        lottery_type=LotteryType.BIG_LOTTO,
        history=_patterned_history(30),
    )
    result = build_production_generate_portfolio().execute(request)

    assert result.status is GeneratePortfolioStatus.OK
    assert result.numbers is not None
    assert len(result.numbers) == 13
    assert result.numbers == BigLottoAprioriStrategyAdapter().get_bets(
        _patterned_history(30), LotteryType.BIG_LOTTO
    )


def test_production_catalog_appends_apriori_last_and_preserves_prior_order() -> None:
    catalog = production_catalog()
    all_ids = tuple(descriptor.strategy_id for descriptor in catalog)
    assert len(all_ids) == 73
    assert all_ids[-1] == STRATEGY_ID
    assert all_ids[:-1].count(STRATEGY_ID) == 0
    assert all_ids[-2] == "legacy_biglotto__minimal_dual_bet_strategy__3c9657df7ff4"
    assert all_ids[-3] == "legacy_biglotto__backtest_biglotto_markov_4bet__aefb54eb345b"
