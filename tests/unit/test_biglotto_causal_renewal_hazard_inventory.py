from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import pytest

from lottolab.application.historical_replay_adapters import BigLottoReplayAdapter
from lottolab.application.native_replay_inventory import native_strategy_inventory
from lottolab.application.replay_strategy_inventory import load_replay_strategy_inventory
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import (
    ReplayBehavior,
    ReplayDraw,
)
from lottolab.domain.replay_strategy_inventory import (
    ReplayDataStatus,
    ReplayExecutionCapability,
    ReplayLifecycleStatus,
)
from lottolab.strategies.adapters.base import InsufficientHistory

STRATEGY_VERSION = "FIXED_DISCRETE_RENEWAL_HAZARD_V1"
STRATEGIES_BY_K = {
    2: "research_causal_renewal_hazard_k2",
    3: "research_causal_renewal_hazard_k3",
    5: "research_causal_renewal_hazard_k5",
}


def _draw(index: int, numbers: tuple[int, ...]) -> ReplayDraw:
    return ReplayDraw(
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number=str(index),
        draw_date=date(2020, 1, 1) + timedelta(days=index - 1),
        main_numbers=numbers,
        special_number=next(number for number in range(49, 0, -1) if number not in numbers),
    )


def _history(count: int) -> tuple[ReplayDraw, ...]:
    return tuple(
        _draw(
            index,
            tuple(sorted(((index * 7 + offset * 11) % 49) + 1 for offset in range(6))),
        )
        for index in range(1, count + 1)
    )


def _renewal_bindings():
    bindings, accounts = native_strategy_inventory(LotteryType.BIG_LOTTO)
    selected = {
        binding.strategy.strategy_id: binding
        for binding in bindings
        if binding.strategy.strategy_id in STRATEGIES_BY_K.values()
    }
    assert set(selected) == set(STRATEGIES_BY_K.values())
    return selected, accounts


def test_native_inventory_binds_exact_k_version_behavior_and_fingerprint() -> None:
    bindings, accounts = _renewal_bindings()
    fingerprints: set[str] = set()

    for ticket_count, strategy_id in STRATEGIES_BY_K.items():
        binding = bindings[strategy_id]
        implementation = binding.implementation
        strategy = binding.strategy

        assert implementation.strategy_id == strategy_id
        assert implementation.strategy_version == STRATEGY_VERSION
        assert implementation.native_ticket_count == ticket_count
        assert strategy.strategy_version == STRATEGY_VERSION
        assert strategy.native_ticket_count == ticket_count
        assert strategy.min_history == 750
        assert strategy.behavior is ReplayBehavior.DETERMINISTIC
        assert strategy.fingerprint is not None and len(strategy.fingerprint) == 64
        assert accounts[strategy_id]["status"] == "EXECUTABLE"
        assert accounts[strategy_id]["fingerprint"] == strategy.fingerprint
        fingerprints.add(strategy.fingerprint)

    assert len(fingerprints) == 3


def test_formal_inventory_reads_three_exact_native_bindings() -> None:
    inventory = load_replay_strategy_inventory()
    renewal_items = [
        item for item in inventory.items if item.strategy_id in STRATEGIES_BY_K.values()
    ]

    assert {(item.strategy_id, item.strategy_version) for item in renewal_items} == {
        (strategy_id, STRATEGY_VERSION) for strategy_id in STRATEGIES_BY_K.values()
    }
    assert len(renewal_items) == 3
    for item in renewal_items:
        ticket_count = next(
            k for k, strategy_id in STRATEGIES_BY_K.items() if strategy_id == item.strategy_id
        )
        assert item.execution_capability is ReplayExecutionCapability.EXECUTABLE
        assert item.adapter_mapping is not None
        assert item.adapter_mapping.replay_adapter == (
            "lottolab.application.historical_replay_adapters.BigLottoReplayAdapter"
        )
        assert item.adapter_mapping.strategy_id == item.strategy_id
        assert item.adapter_mapping.strategy_version == STRATEGY_VERSION
        assert item.adapter_mapping.implementation_locator.endswith(
            f"BigLottoCausalRenewalHazardK{ticket_count}Adapter"
        )
        assert item.backfill_native_binding is True
        assert item.lifecycle_status is ReplayLifecycleStatus.UNREGISTERED_IDENTIFIED
        assert item.replay_data_status is ReplayDataStatus.RECONSTRUCTABLE


def test_native_replay_generates_scores_and_rejects_wrong_identity_or_short_history() -> None:
    bindings, _accounts = _renewal_bindings()
    adapter = BigLottoReplayAdapter(tuple(bindings.values()))
    history = _history(750)
    target = _draw(751, (1, 2, 3, 4, 5, 6))
    alternate_target = _draw(752, (40, 41, 42, 43, 44, 45))

    assert len(history) == 750
    assert history[-1].draw_number == "750"
    assert all(draw.draw_number != target.draw_number for draw in history)

    for ticket_count, strategy_id in STRATEGIES_BY_K.items():
        strategy = bindings[strategy_id].strategy
        tickets = adapter.generate(strategy, history, target)
        assert len(tickets) == ticket_count
        assert tuple(ticket.ticket_position for ticket in tickets) == tuple(
            range(1, ticket_count + 1)
        )
        assert all(
            len(ticket.main_numbers) == 6
            and tuple(sorted(ticket.main_numbers)) == ticket.main_numbers
            and len(set(ticket.main_numbers)) == 6
            and all(1 <= number <= 49 for number in ticket.main_numbers)
            for ticket in tickets
        )
        assert adapter.generate(strategy, history, alternate_target) == tickets

        matching_target = _draw(751, tickets[0].main_numbers)
        nonmatching_numbers = tuple(
            number for number in range(1, 50) if number not in tickets[0].main_numbers
        )[:6]
        nonmatching_target = _draw(752, nonmatching_numbers)
        matching_score = adapter.evaluate(strategy, tickets[0], matching_target)
        nonmatching_score = adapter.evaluate(strategy, tickets[0], nonmatching_target)
        assert matching_score.zone1_hits == 6
        assert nonmatching_score.zone1_hits == 0

        with pytest.raises(InsufficientHistory):
            adapter.generate(strategy, history[:-1], target)

        wrong_version = replace(strategy, strategy_version="OTHER_RENEWAL_VERSION")
        with pytest.raises(ValueError, match="identity is not pinned"):
            adapter.generate(wrong_version, history, target)
