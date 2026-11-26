from __future__ import annotations

import hashlib
from datetime import date, timedelta
from importlib.metadata import version as distribution_version
from pathlib import Path

import pytest

from lottolab.application.historical_replay_adapters import BigLottoReplayAdapter
from lottolab.application.native_replay_inventory import native_strategy_inventory
from lottolab.application.replay_strategy_inventory import load_replay_strategy_inventory
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayBehavior, ReplayDraw
from lottolab.domain.replay_strategy_inventory import (
    ReplayDataStatus,
    ReplayExecutionCapability,
    ReplayLifecycleStatus,
)
from lottolab.strategies.adapters.base import CausalDrawRow, InsufficientHistory

RENEWAL_VERSION = "FIXED_DISCRETE_RENEWAL_HAZARD_V1"
TE_VERSION = "EH02_V1"
STRATEGIES_BY_ID = {
    "research_causal_renewal_hazard_k2": (
        RENEWAL_VERSION,
        2,
        "BigLottoCausalRenewalHazardK2Adapter",
    ),
    "research_causal_renewal_hazard_k3": (
        RENEWAL_VERSION,
        3,
        "BigLottoCausalRenewalHazardK3Adapter",
    ),
    "research_causal_renewal_hazard_k5": (
        RENEWAL_VERSION,
        5,
        "BigLottoCausalRenewalHazardK5Adapter",
    ),
    "research_conditional_transfer_entropy_k2": (TE_VERSION, 2, "BigLottoConditionalTEK2Adapter"),
    "research_conditional_transfer_entropy_k3": (TE_VERSION, 3, "BigLottoConditionalTEK3Adapter"),
    "research_conditional_transfer_entropy_k5": (TE_VERSION, 5, "BigLottoConditionalTEK5Adapter"),
}
COMMON_FINGERPRINT_SOURCES = {
    "src/lottolab/application/native_replay_inventory.py",
    "src/lottolab/application/historical_replay_adapters.py",
    "src/lottolab/application/replay_strategy_inventory.py",
    "src/lottolab/domain/draws.py",
    "src/lottolab/domain/historical_replay.py",
    "src/lottolab/domain/lottery_rules.py",
    "src/lottolab/domain/prize_evaluation.py",
    "src/lottolab/strategies/adapters/base.py",
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


def _native_bindings():
    bindings, accounts = native_strategy_inventory(LotteryType.BIG_LOTTO)
    strategy_ids = [binding.strategy.strategy_id for binding in bindings]
    selected = {
        binding.strategy.strategy_id: binding
        for binding in bindings
        if binding.strategy.strategy_id in STRATEGIES_BY_ID
    }
    assert len(selected) == 6
    assert {strategy_id: strategy_ids.count(strategy_id) for strategy_id in STRATEGIES_BY_ID} == {
        strategy_id: 1 for strategy_id in STRATEGIES_BY_ID
    }
    return selected, accounts


def test_native_inventory_returns_six_exact_fingerprinted_bindings() -> None:
    selected, accounts = _native_bindings()
    fingerprints: set[str] = set()
    project_root = Path(__file__).resolve().parents[2]

    for strategy_id, (version, ticket_count, class_name) in STRATEGIES_BY_ID.items():
        binding = selected[strategy_id]
        implementation = binding.implementation
        strategy = binding.strategy
        assert type(implementation).__name__ == class_name
        assert implementation.strategy_id == strategy_id
        assert implementation.strategy_version == version
        assert implementation.native_ticket_count == ticket_count
        assert implementation.min_history == 750
        assert strategy.strategy_version == version
        assert strategy.native_ticket_count == ticket_count
        assert strategy.min_history == 750
        assert strategy.behavior is ReplayBehavior.DETERMINISTIC
        assert strategy.fingerprint is not None and len(strategy.fingerprint) == 64
        assert accounts[strategy_id]["status"] == "EXECUTABLE"
        assert accounts[strategy_id]["fingerprint"] == strategy.fingerprint

        source_hashes = accounts[strategy_id]["implementation_fingerprint_source_sha256"]
        runtime_dependencies = accounts[strategy_id][
            "implementation_fingerprint_runtime_dependencies"
        ]
        algorithm_source = (
            "src/lottolab/strategies/adapters/biglotto_causal_renewal_hazard.py"
            if strategy_id.startswith("research_causal_renewal_hazard_")
            else "src/lottolab/strategies/adapters/biglotto_conditional_te.py"
        )
        assert set(source_hashes) == COMMON_FINGERPRINT_SOURCES | {algorithm_source}
        assert all(
            hashlib.sha256((project_root / relative_path).read_bytes()).hexdigest() == source_hash
            for relative_path, source_hash in source_hashes.items()
        )
        assert runtime_dependencies == (
            {"numpy": distribution_version("numpy")}
            if strategy_id.startswith("research_conditional_transfer_entropy_")
            else {}
        )
        fingerprints.add(strategy.fingerprint)

    repeated, _accounts = _native_bindings()
    assert {key: value.strategy.fingerprint for key, value in selected.items()} == {
        key: value.strategy.fingerprint for key, value in repeated.items()
    }
    assert len(fingerprints) == 6


def test_formal_loader_reads_six_exact_executable_native_mappings() -> None:
    inventory = load_replay_strategy_inventory()
    selected = [item for item in inventory.items if item.strategy_id in STRATEGIES_BY_ID]
    assert len(selected) == 6
    assert {(item.strategy_id, item.strategy_version) for item in selected} == {
        (strategy_id, version)
        for strategy_id, (version, _ticket_count, _class_name) in STRATEGIES_BY_ID.items()
    }

    for item in selected:
        _version, _ticket_count, class_name = STRATEGIES_BY_ID[item.strategy_id]
        assert item.execution_capability is ReplayExecutionCapability.EXECUTABLE
        assert item.adapter_mapping is not None
        assert item.adapter_mapping.replay_adapter == (
            "lottolab.application.historical_replay_adapters.BigLottoReplayAdapter"
        )
        assert item.adapter_mapping.strategy_id == item.strategy_id
        assert item.adapter_mapping.strategy_version == STRATEGIES_BY_ID[item.strategy_id][0]
        assert item.adapter_mapping.implementation_locator.endswith(class_name)
        assert item.backfill_native_binding is True
        assert item.lifecycle_status is ReplayLifecycleStatus.UNREGISTERED_IDENTIFIED
        assert item.replay_data_status is ReplayDataStatus.RECONSTRUCTABLE


def test_standard_native_replay_generates_deterministically_and_scores_target_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected, _accounts = _native_bindings()
    adapter = BigLottoReplayAdapter(tuple(selected.values()))
    history = _history(750)
    target = _draw(751, (1, 2, 3, 4, 5, 6))
    alternate_target = _draw(752, (40, 41, 42, 43, 44, 45))
    expected_producer_input = tuple(
        CausalDrawRow(
            draw=draw.draw_number,
            date=draw.draw_date.isoformat(),
            numbers=draw.main_numbers,
        )
        for draw in history
    )
    observed_producer_inputs: list[tuple[str, tuple[CausalDrawRow, ...]]] = []

    for binding in selected.values():
        adapter_type = type(binding.implementation)
        original_predict = adapter_type._predict_all

        def capture_input(
            implementation,
            producer_history,
            lottery_type,
            *,
            original=original_predict,
        ):
            observed_producer_inputs.append((implementation.strategy_id, producer_history))
            return original(implementation, producer_history, lottery_type)

        monkeypatch.setattr(adapter_type, "_predict_all", capture_input)

    first_run = {
        strategy_id: adapter.generate(binding.strategy, history, target)
        for strategy_id, binding in selected.items()
    }
    for strategy_id, binding in selected.items():
        ticket_count = STRATEGIES_BY_ID[strategy_id][1]
        tickets = first_run[strategy_id]
        assert tickets == adapter.generate(binding.strategy, history, target)
        assert tickets == adapter.generate(binding.strategy, history, alternate_target)
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

        producer_inputs = [
            observed
            for observed_id, observed in observed_producer_inputs
            if observed_id == strategy_id
        ]
        assert len(producer_inputs) == 3
        assert producer_inputs == [
            expected_producer_input,
            expected_producer_input,
            expected_producer_input,
        ]
        assert all(
            row.draw not in {target.draw_number, alternate_target.draw_number}
            for producer_input in producer_inputs
            for row in producer_input
        )

        matching_target = _draw(751, tickets[0].main_numbers)
        nonmatching_numbers = tuple(
            number for number in range(1, 50) if number not in tickets[0].main_numbers
        )[:6]
        nonmatching_target = _draw(752, nonmatching_numbers)
        assert adapter.evaluate(binding.strategy, tickets[0], matching_target).zone1_hits == 6
        assert adapter.evaluate(binding.strategy, tickets[0], nonmatching_target).zone1_hits == 0

        try:
            adapter.generate(binding.strategy, history[:-1], target)
        except InsufficientHistory:
            pass
        else:
            raise AssertionError(f"{strategy_id} accepted 749 history rows")
