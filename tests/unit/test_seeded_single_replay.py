"""Regression checks for the per-target reproducible replay contract."""

from __future__ import annotations

import random
from dataclasses import replace
from datetime import date, timedelta

import pytest

from lottolab.application.historical_replay_adapters import (
    BigLottoReplayAdapter,
    binding_from_implementation,
)
from lottolab.application.replay_strategy_inventory import _production_binding
from lottolab.application.seeded_single_replay import (
    SEED_CONTRACT,
    SeededSingleTicketReplay,
    replay_seed,
)
from lottolab.application.use_cases.historical_replay_controller import HistoricalReplayController
from lottolab.application.use_cases.replay_backfill import ReplayBackfill
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayBehavior, ReplayDraw
from lottolab.strategies.adapters.biglotto_frontend_ml import (
    BigLottoFrontendMLFeatureWeightedAdapter,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry


def _draws() -> tuple[ReplayDraw, ...]:
    return tuple(
        ReplayDraw(
            LotteryType.BIG_LOTTO,
            str(i + 100),
            date(2020, 1, 1) + timedelta(days=i),
            tuple(sorted(((i + 7 * j) % 49) + 1 for j in range(6))),
            49,
        )
        for i in range(31)
    )


def test_repeat_is_independent_of_global_random_and_target_outcome() -> None:
    draws = _draws()
    adapter = SeededSingleTicketReplay(
        "test-id", "test-name", "v0.1", 1, BigLottoFrontendMLFeatureWeightedAdapter
    )
    first = adapter.get_replay_tickets(draws[:-1], draws[-1])
    for _ in range(500):
        random.random()
    changed_target = replace(draws[-1], main_numbers=(1, 2, 3, 4, 5, 6))
    assert adapter.get_replay_tickets(draws[:-1], changed_target) == first
    assert adapter.strategy_version == "v0.1+seeded-replay-v1"
    assert SEED_CONTRACT == "seeded-single-causal-history-sha256-v1"
    assert replay_seed("test-id", draws[:-1]) != replay_seed("other-id", draws[:-1])


def test_future_history_is_rejected() -> None:
    draws = _draws()
    adapter = SeededSingleTicketReplay(
        "test-id", "test-name", "v0.1", 1, BigLottoFrontendMLFeatureWeightedAdapter
    )
    with pytest.raises(ValueError, match="strictly precede"):
        adapter.get_replay_tickets(draws, draws[-1])


def test_controller_binding_declares_seeded_behavior_and_repeats() -> None:
    draws = _draws()
    impl = SeededSingleTicketReplay(
        "test-id", "test-name", "v0.1", 1, BigLottoFrontendMLFeatureWeightedAdapter
    )
    binding = binding_from_implementation(
        impl, behavior=ReplayBehavior.SEEDED_STOCHASTIC, seed_contract=SEED_CONTRACT
    )
    controller = HistoricalReplayController(BigLottoReplayAdapter((binding,)))
    first = controller._generate_cell(binding.strategy, draws[-1], draws[:-1])
    changed_target = replace(draws[-1], main_numbers=(1, 2, 3, 4, 5, 6))
    second = controller._generate_cell(binding.strategy, changed_target, draws[:-1])
    assert first.status.value == second.status.value == "COMPLETE"
    assert first.tickets == second.tickets
    assert binding.strategy.behavior is ReplayBehavior.SEEDED_STOCHASTIC
    assert binding.strategy.seed_contract == SEED_CONTRACT


def test_inventory_marks_only_live_unseeded_rng_as_nondeterministic() -> None:
    catalog = production_catalog()
    registry = ExecutableRegistry(catalog)
    ids = {
        "legacy_biglotto__frontend_ml_features__3a4324bc2aa9": (
            ReplayBehavior.LEGACY_NONDETERMINISTIC
        ),
        "legacy_biglotto__backtest_apriori__2abb53765703": ReplayBehavior.DETERMINISTIC,
        "legacy_biglotto__frontend_auto_optimize_strategy__a121d28125c6": (
            ReplayBehavior.DETERMINISTIC
        ),
    }
    for strategy_id, expected in ids.items():
        binding, error = _production_binding(
            catalog.get(strategy_id), registry, LotteryType.BIG_LOTTO
        )
        assert error is None and binding is not None
        assert binding.strategy.behavior is expected


def test_unseeded_inventory_binding_fails_closed_at_backfill_boundary() -> None:
    catalog = production_catalog()
    strategy_id = "legacy_biglotto__frontend_ml_features__3a4324bc2aa9"
    binding, error = _production_binding(
        catalog.get(strategy_id), ExecutableRegistry(catalog), LotteryType.BIG_LOTTO
    )
    assert error is None and binding is not None
    with pytest.raises(ValueError, match="require a pinned seed"):
        ReplayBackfill(
            adapter=BigLottoReplayAdapter((binding,)),
            strategies=(binding.strategy,),
            draws=_draws(),
            source_identity="test-source",
            store=None,  # type: ignore[arg-type]
            execution_version="test-version",
        )
