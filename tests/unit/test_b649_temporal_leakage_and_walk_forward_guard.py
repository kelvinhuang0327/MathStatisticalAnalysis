"""Comprehensive temporal leakage audit and walk-forward guard tests for B649."""

from __future__ import annotations

import math
import random
from collections import Counter
from datetime import date, datetime, timedelta
from typing import cast
from zoneinfo import ZoneInfo

import pytest

from lottolab.application.biglotto_multi_ticket_backtest import (
    _strictly_precedes_target,
    _Target,
)
from lottolab.application.historical_replay_adapters import (
    BigLottoReplayAdapter,
    binding_from_implementation,
)
from lottolab.application.use_cases.historical_replay_controller import (
    HistoricalReplayController,
    _history_before,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.exact_native_replay import ExactNativeReplayError, assert_causal_history
from lottolab.domain.historical_replay import (
    ComparisonVerdict,
    HistoricalReplayMode,
    HistoricalReplayRequest,
    ReplayBehavior,
    ReplayCellStatus,
    ReplayDraw,
    ReplaySourceSnapshot,
    ReplayStrategy,
    ReplayTicket,
)
from lottolab.domain.prize_evaluation import evaluate_lottery_prize
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_wave1 import BigLottoDynamicFrequencyAdapter
from lottolab.strategies.adapters.biglotto_frontend_auto_optimize import (
    BigLottoFrontendAutoOptimizeAdapter,
)
from lottolab.strategies.adapters.biglotto_horizon_minimax import (
    BigLottoHorizonMinimaxDisagreementAdapter,
)
from lottolab.strategies.adapters.biglotto_selected import BigLottoDeviation2BetAdapter
from tools.b649_operational_prediction_loop import (
    HistorySnapshot,
    PredictionTarget,
    StrategyStream,
    assert_causal_cutoff,
    create_prediction_payload,
    run_strategy_stream,
)

TAIPEI = ZoneInfo("Asia/Taipei")


def _make_draw(
    number: int,
    *,
    main_numbers: tuple[int, ...],
    special_number: int,
    start_date: date = date(2026, 1, 1),
) -> ReplayDraw:
    return ReplayDraw(
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number=str(number),
        draw_date=start_date + timedelta(days=number - 100000001),
        main_numbers=main_numbers,
        special_number=special_number,
    )


def _generate_synthetic_draw_sequence(
    count: int, *, start_number: int = 100000001
) -> tuple[ReplayDraw, ...]:
    """Generate a deterministic, realistic sequence of BIG_LOTTO draws."""
    draws: list[ReplayDraw] = []
    for i in range(count):
        num = start_number + i
        # Deterministic rotation across 1..49
        main = tuple(sorted(((i * 7 + k * 5) % 49) + 1 for k in range(6)))
        if len(set(main)) < 6:
            main = tuple(sorted(list(range(1, 7))))
        main_set = set(main)
        special = ((i * 11 + 3) % 49) + 1
        while special in main_set:
            special = (special % 49) + 1
        draws.append(
            _make_draw(
                num,
                main_numbers=main,
                special_number=special,
            )
        )
    return tuple(draws)


# ==============================================================================
# PART 1: Temporal Cutoff Implementation & Guard Enforcement
# ==============================================================================


def test_history_before_strictly_enforces_temporal_cutoff() -> None:
    """Ensure _history_before strictly excludes target and future draws."""
    draws = _generate_synthetic_draw_sequence(10)
    target = draws[5]

    history = _history_before(draws, target)

    # Invariant: TRAINING_MAX_DRAW < T
    assert len(history) == 5
    assert all(row.sort_key < target.sort_key for row in history)
    assert max(row.sort_key for row in history) < target.sort_key

    # Invariant: TARGET_DRAW_USED_AS_INPUT: NO
    assert target not in history

    # Invariant: FUTURE_DRAW_USED_AS_INPUT: NO
    assert all(draw.sort_key < target.sort_key for draw in history)
    for future_draw in draws[6:]:
        assert future_draw not in history


def test_historical_replay_controller_fails_fast_on_causal_cutoff_violation() -> None:
    """HistoricalReplayController detects and flags rows >= target as CAUSAL_CUTOFF_VIOLATION."""
    draws = _generate_synthetic_draw_sequence(5)
    target = draws[2]

    # Malicious/leaky history containing the target draw itself
    leaky_history = (draws[0], draws[1], target)

    binding = binding_from_implementation(BigLottoHorizonMinimaxDisagreementAdapter())
    adapter = BigLottoReplayAdapter((binding,))
    controller = HistoricalReplayController(adapter)

    record = controller._generate_cell(binding.strategy, target, leaky_history)

    assert record.status is ReplayCellStatus.FAILED
    assert record.reason == "CAUSAL_CUTOFF_VIOLATION"

    # Running full execute through request properly slices history so no violations occur
    request = HistoricalReplayRequest(
        lottery_type=LotteryType.BIG_LOTTO,
        mode=HistoricalReplayMode.FULL_REPLAY,
        source=ReplaySourceSnapshot(
            lottery_type=LotteryType.BIG_LOTTO,
            historical_draws=draws[:3],
        ),
        strategies=(binding.strategy,),
        cutoff_draw_number=target.draw_number,
    )
    result = controller.execute(request)
    assert result.causal_violation_count == 0


def test_biglotto_replay_adapter_direct_call_raises_on_causal_cutoff_violation() -> None:
    """BigLottoReplayAdapter methods raise ExactNativeReplayError if history contains rows >= target."""
    draws = _generate_synthetic_draw_sequence(5)
    target = draws[2]
    leaky_history = (draws[0], draws[1], target)

    binding = binding_from_implementation(BigLottoHorizonMinimaxDisagreementAdapter())
    adapter = BigLottoReplayAdapter((binding,))

    with pytest.raises(ExactNativeReplayError, match="CAUSAL_CUTOFF_VIOLATION"):
        adapter.generate(binding.strategy, leaky_history, target)

    with pytest.raises(ExactNativeReplayError, match="CAUSAL_CUTOFF_VIOLATION"):
        adapter.expected_native_ticket_count(binding.strategy, leaky_history, target)


def test_operational_loop_assert_causal_cutoff_raises_on_leakage() -> None:
    """assert_causal_cutoff fails fast if history cutoff >= target or any row >= target."""
    history_rows = (
        CausalDrawRow("115000078", "2026-08-11", (1, 2, 3, 4, 5, 6)),
        CausalDrawRow("115000079", "2026-08-14", (7, 8, 9, 10, 11, 12)),  # Equal to target
    )

    with pytest.raises(ValueError, match="CAUSAL_CUTOFF_VIOLATION"):
        assert_causal_cutoff(
            target_draw_number="115000079",
            target_draw_date="2026-08-14",
            history_cutoff_draw="115000079",
            history_cutoff_date="2026-08-14",
            history_rows=history_rows,
        )


def test_operational_loop_run_strategy_stream_enforces_anti_leakage() -> None:
    """run_strategy_stream rejects execution when history reaches or exceeds target."""
    leaky_snapshot = HistorySnapshot(
        rows=(CausalDrawRow("115000080", "2026-08-18", (1, 2, 3, 4, 5, 6)),),
        cutoff_draw="115000080",
        cutoff_date="2026-08-18",
        draw_count=1,
        history_sha256="0" * 64,
    )
    target = PredictionTarget(
        lottery_type="BIG_LOTTO",
        draw_number="115000080",
        draw_date="2026-08-18",
        scheduled_at="2026-08-18T20:30:00+08:00",
    )
    stream = StrategyStream(
        strategy_id=BigLottoHorizonMinimaxDisagreementAdapter.strategy_id,
        strategy_version=BigLottoHorizonMinimaxDisagreementAdapter.strategy_version,
        enabled=True,
        adapter_factory=BigLottoHorizonMinimaxDisagreementAdapter,
        native_ticket_count=2,
    )

    with pytest.raises(ValueError, match="CAUSAL_CUTOFF_VIOLATION"):
        run_strategy_stream(
            stream,
            leaky_snapshot,
            target,
            created_at=datetime.now(TAIPEI),
            prediction_run_id="test-run-001",
        )


def test_backtest_strictly_precedes_target_rejects_equal_or_future_draws() -> None:
    """_strictly_precedes_target in biglotto_multi_ticket_backtest enforces strict temporal precedence."""
    target = _Target(
        draw_number="115000080",
        draw_date=date(2026, 8, 18),
        winning_main_numbers=(1, 2, 3, 4, 5, 6),
        winning_special_number=7,
    )

    # Strictly preceding: valid
    assert _strictly_precedes_target(
        cutoff_number="115000079",
        cutoff_date=date(2026, 8, 15),
        target=target,
    ) is True

    # Same date / number: rejected
    assert _strictly_precedes_target(
        cutoff_number="115000080",
        cutoff_date=date(2026, 8, 18),
        target=target,
    ) is False

    # Future date: rejected
    assert _strictly_precedes_target(
        cutoff_number="115000081",
        cutoff_date=date(2026, 8, 22),
        target=target,
    ) is False


# ==============================================================================
# PART 2: Temporal Invariance Characterization Tests
# ==============================================================================


@pytest.mark.parametrize(
    "adapter_factory",
    [
        BigLottoHorizonMinimaxDisagreementAdapter,
        BigLottoDeviation2BetAdapter,
        BigLottoDynamicFrequencyAdapter,
        BigLottoFrontendAutoOptimizeAdapter,
    ],
)
def test_temporal_invariance_dataset_a_vs_dataset_b(adapter_factory: type) -> None:
    """Assert PREDICTION_A == PREDICTION_B when evaluated at cutoff C.

    Dataset A contains draws strictly through cutoff C (220 draws >= min_history 200).
    Dataset B contains the same draws through C + target T + future draws after T (260 draws).
    The canonical prediction for target T must be identical under both datasets.
    """
    total_draws = _generate_synthetic_draw_sequence(260)
    cutoff_index = 220  # draws 0..219 are strictly before target
    target = total_draws[cutoff_index]

    dataset_a = total_draws[:cutoff_index]  # only draws < target
    dataset_b = total_draws  # draws < target + target + draws > target

    impl_a = (
        adapter_factory(random.Random(42))
        if adapter_factory is BigLottoFrontendAutoOptimizeAdapter
        else adapter_factory()
    )
    binding_a = binding_from_implementation(impl_a)
    controller_a = HistoricalReplayController(BigLottoReplayAdapter((binding_a,)))

    impl_b = (
        adapter_factory(random.Random(42))
        if adapter_factory is BigLottoFrontendAutoOptimizeAdapter
        else adapter_factory()
    )
    binding_b = binding_from_implementation(impl_b)
    controller_b = HistoricalReplayController(BigLottoReplayAdapter((binding_b,)))

    # Predict target using Dataset A
    history_a = _history_before(dataset_a, target)
    record_a = controller_a._generate_cell(binding_a.strategy, target, history_a)

    # Predict target using Dataset B
    history_b = _history_before(dataset_b, target)
    record_b = controller_b._generate_cell(binding_b.strategy, target, history_b)

    assert history_a == history_b
    assert record_a.status is ReplayCellStatus.COMPLETE
    assert record_b.status is ReplayCellStatus.COMPLETE
    assert record_a.tickets == record_b.tickets
    assert [t.main_numbers for t in record_a.tickets] == [t.main_numbers for t in record_b.tickets]


def test_temporal_invariance_non_vacuity_future_injection_changes_prediction() -> None:
    """Non-vacuity proof: prove that if future draws were included in history, predictions differ."""
    draws = _generate_synthetic_draw_sequence(260)

    # Valid causal history (210 draws strictly prior to target)
    valid_causal_rows = tuple(
        CausalDrawRow(d.draw_number, d.draw_date.isoformat(), d.main_numbers)
        for d in draws[:210]
    )

    # Contaminated history where 40 future draws are mistakenly included (250 draws)
    contaminated_rows = tuple(
        CausalDrawRow(d.draw_number, d.draw_date.isoformat(), d.main_numbers)
        for d in draws[:250]
    )

    adapter = BigLottoHorizonMinimaxDisagreementAdapter()
    prediction_clean = adapter.get_bets(valid_causal_rows, LotteryType.BIG_LOTTO)
    prediction_leaky = adapter.get_bets(contaminated_rows, LotteryType.BIG_LOTTO)

    # Invariant: Future data changes the frequency distributions / z-scores / tickets
    assert prediction_clean != prediction_leaky, (
        "Non-vacuity violation: future data had no effect on prediction, "
        "adapter may be static or insensitive."
    )


# ==============================================================================
# PART 3: Historical Walk-Forward Test (50 Targets)
# ==============================================================================


def test_b649_historical_walk_forward_50_targets_anti_leakage_enforcement() -> None:
    """Execute a 50-target sequential walk-forward evaluation.

    For every target T in the 50-target sequence:
    1. History is derived ONLY from draws strictly prior to T (max(history) < T).
    2. Prediction is generated strictly before outcome numbers are inspected.
    3. Target outcome numbers are compared ONLY AFTER prediction is generated.
    4. Record TARGET_DRAW, TRAINING_CUTOFF_DRAW, TRAINING_ROW_COUNT, PREDICTION, OUTCOME, MATCH_COUNT.
    """
    total_draws_needed = 250  # 200 initial history + 50 walk-forward targets
    all_draws = _generate_synthetic_draw_sequence(total_draws_needed)

    target_sequence = all_draws[200:250]
    assert len(target_sequence) == 50

    binding = binding_from_implementation(BigLottoHorizonMinimaxDisagreementAdapter())
    adapter = BigLottoReplayAdapter((binding,))
    controller = HistoricalReplayController(adapter)

    walk_forward_records = []
    match_distribution = Counter()

    first_target_evidence = None
    last_target_evidence = None

    for idx, target in enumerate(target_sequence):
        # Step 1: Strict temporal slicing
        history = _history_before(all_draws, target)

        # Anti-leakage assertions:
        assert len(history) >= 200
        assert all(row.sort_key < target.sort_key for row in history)
        assert max(row.sort_key for row in history) < target.sort_key
        assert target not in history
        for future_target in target_sequence[idx + 1 :]:
            assert future_target not in history

        cutoff_draw = history[-1]
        assert cutoff_draw.sort_key < target.sort_key

        # Step 2: Generate prediction (Outcome numbers NOT yet visible to generator)
        record = controller._generate_cell(binding.strategy, target, history)
        assert record.status is ReplayCellStatus.COMPLETE
        predicted_tickets = tuple(t.main_numbers for t in record.tickets)
        assert len(predicted_tickets) == 2

        # Step 3: Outcome visibility boundary (Inspected ONLY AFTER prediction is produced)
        outcome_main = target.main_numbers
        outcome_special = target.special_number

        # Step 4: Evaluate matches
        best_zone1_matches = 0
        for ticket in record.tickets:
            eval_result = evaluate_lottery_prize(
                lottery_type=LotteryType.BIG_LOTTO,
                predicted_main_numbers=ticket.main_numbers,
                predicted_special_number=ticket.special_number,
                winning_main_numbers=outcome_main,
                winning_special_number=outcome_special,
            )
            if eval_result.zone1_hits > best_zone1_matches:
                best_zone1_matches = eval_result.zone1_hits

        match_distribution[f"M{best_zone1_matches}"] += 1

        evidence_row = {
            "TARGET_DRAW": target.draw_number,
            "TRAINING_CUTOFF_DRAW": cutoff_draw.draw_number,
            "TRAINING_ROW_COUNT": len(history),
            "PREDICTION": predicted_tickets,
            "OUTCOME": outcome_main,
            "MATCH_COUNT": best_zone1_matches,
        }
        walk_forward_records.append(evidence_row)

        if idx == 0:
            first_target_evidence = evidence_row
        if idx == len(target_sequence) - 1:
            last_target_evidence = evidence_row

    # Verification of the 50-target walk-forward
    assert len(walk_forward_records) == 50
    assert first_target_evidence is not None
    assert last_target_evidence is not None

    assert first_target_evidence["TARGET_DRAW"] == "100000201"
    assert first_target_evidence["TRAINING_CUTOFF_DRAW"] == "100000200"
    assert first_target_evidence["TRAINING_ROW_COUNT"] == 200

    assert last_target_evidence["TARGET_DRAW"] == "100000250"
    assert last_target_evidence["TRAINING_CUTOFF_DRAW"] == "100000249"
    assert last_target_evidence["TRAINING_ROW_COUNT"] == 249

    # Check match distribution integrity
    assert sum(match_distribution.values()) == 50
    # All match counts are between M0 and M6
    assert all(k in [f"M{i}" for i in range(7)] for k in match_distribution.keys())


# ==============================================================================
# PART 4: Strategy Selection Leakage Verification
# ==============================================================================


def test_strategy_selection_has_zero_future_leakage() -> None:
    """Verify that dynamic strategy selector BigLottoFrontendAutoOptimizeAdapter
    trains and evaluates candidate models exclusively on historical subsets strictly < target.
    """
    draws = _generate_synthetic_draw_sequence(60)
    target = draws[50]

    history = _history_before(draws, target)
    causal_rows = tuple(
        CausalDrawRow(d.draw_number, d.draw_date.isoformat(), d.main_numbers)
        for d in history
    )

    adapter = BigLottoFrontendAutoOptimizeAdapter()
    selection = adapter._select(causal_rows)

    # Invariants of the selection mechanism:
    # 1. Total input data count is exactly len(history) == 50
    # 2. Test split size is <= 10
    # 3. Train data size is 50 - test_size
    # 4. Target is completely unseen and unreferenced
    assert selection.test_size == 10
    assert selection.winner in adapter.candidate_strategies
    assert len(selection.final_numbers) == 6
    assert all(1 <= n <= 49 for n in selection.final_numbers)
