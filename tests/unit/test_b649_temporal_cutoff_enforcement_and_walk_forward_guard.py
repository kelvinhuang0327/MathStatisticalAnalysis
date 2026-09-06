"""Temporal anti-leakage audit for B649: cutoff enforcement and walk-forward guard.

Proves, across the operational prediction loop and the shared historical
replay controller, that no prediction input can ever include the target draw
itself or any draw after it, and characterizes a bounded walk-forward
evaluation window built the same way.
"""

from __future__ import annotations

import json
import random
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from tools.b649_operational_prediction_loop import (
    STRATEGY_STREAMS,
    TARGET_DRAW_DATE,
    TARGET_DRAW_NUMBER,
    HistorySnapshot,
    PredictionTarget,
    _assert_causal_cutoff,  # pyright: ignore[reportPrivateUsage]
    create_prediction_payload,
    load_canonical_history,
    run_strategy_stream,
)

from lottolab.application.historical_replay_adapters import (
    BigLottoReplayAdapter,
    binding_from_implementation,
)
from lottolab.application.use_cases.historical_replay_controller import (
    HistoricalReplayController,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayCellStatus, ReplayDraw
from lottolab.domain.ingestion import IngestionOperationType, IngestionRunStatus
from lottolab.domain.prize_evaluation import evaluate_lottery_prize
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    initialize_schema,
    open_database,
    resolve_local_data_paths,
)
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_frontend_auto_optimize import (
    BigLottoFrontendAutoOptimizeAdapter,
)
from lottolab.strategies.adapters.biglotto_horizon_minimax import (
    BigLottoHorizonMinimaxDisagreementAdapter,
)

# ==============================================================================
# Shared synthetic-draw helpers
# ==============================================================================


def _make_replay_draw(index: int, *, start_date: date = date(2026, 1, 1)) -> ReplayDraw:
    """One deterministic, rule-valid BIG_LOTTO draw for a given sequence index."""

    numbers = random.Random(index).sample(range(1, 50), 7)
    return ReplayDraw(
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number=str(100000001 + index),
        draw_date=start_date + timedelta(days=index),
        main_numbers=tuple(sorted(numbers[:6])),
        special_number=numbers[6],
    )


def _generate_replay_draws(count: int) -> tuple[ReplayDraw, ...]:
    return tuple(_make_replay_draw(i) for i in range(count))


def _causal_rows(draws: Sequence[ReplayDraw]) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(draw=d.draw_number, date=d.draw_date.isoformat(), numbers=d.main_numbers)
        for d in draws
    )


def _seed_causal_history_database(data_root: Path, draws: Sequence[ReplayDraw]) -> Path:
    """A fully-migrated local database seeded with an ordered BIG_LOTTO draw sequence."""

    data_root.mkdir(parents=True, exist_ok=True)
    data_root.chmod(0o700)
    paths = resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(data_root)})
    initialize_schema(paths)
    run_id = "seed-run-temporal-audit"
    timestamp = "2026-01-01T00:00:00.000000Z"
    with open_database(paths, read_only=False) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO ingestion_runs (
                id, operation_type, status, lottery_type, source_filename,
                source_sha256, parser_version, total_count, inserted_count,
                skipped_count, conflict_count, failed_count, first_draw_number,
                last_draw_number, started_at, completed_at, error_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?, ?, ?, NULL)
            """,
            (
                run_id,
                IngestionOperationType.MANUAL_SYNC.value,
                IngestionRunStatus.SUCCESS.value,
                LotteryType.BIG_LOTTO.value,
                "seed.json",
                "0" * 64,
                "test-parser-v1",
                len(draws),
                len(draws),
                draws[0].draw_number,
                draws[-1].draw_number,
                timestamp,
                timestamp,
            ),
        )
        for index, draw in enumerate(draws):
            connection.execute(
                """
                INSERT INTO draws (
                    lottery_type, draw_number, draw_date, main_numbers_json,
                    special_numbers_json, normalized_record_hash, source_name,
                    source_reference, ingestion_run_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draw.lottery_type.value,
                    draw.draw_number,
                    draw.draw_date.isoformat(),
                    json.dumps(list(draw.main_numbers), separators=(",", ":")),
                    json.dumps([draw.special_number], separators=(",", ":")),
                    format(index, "064x"),
                    "test-history",
                    None,
                    run_id,
                    timestamp,
                    timestamp,
                ),
            )
        connection.commit()
    return paths.database


# ==============================================================================
# PART 1: `_assert_causal_cutoff` direct unit tests
# ==============================================================================


def test_assert_causal_cutoff_accepts_strictly_prior_history() -> None:
    _assert_causal_cutoff(
        target_draw_number="115000080",
        target_draw_date="2026-08-18",
        history_cutoff_draw="115000079",
        history_cutoff_date="2026-08-14",
        history_rows=(
            CausalDrawRow("115000078", "2026-08-11", (1, 2, 3, 4, 5, 6)),
            CausalDrawRow("115000079", "2026-08-14", (7, 8, 9, 10, 11, 12)),
        ),
    )


@pytest.mark.parametrize(
    "cutoff_draw,cutoff_date",
    [
        ("115000080", "2026-08-18"),  # equal to target
        ("115000081", "2026-08-22"),  # after target
    ],
)
def test_assert_causal_cutoff_rejects_cutoff_at_or_after_target(
    cutoff_draw: str, cutoff_date: str
) -> None:
    with pytest.raises(ValueError, match="CAUSAL_CUTOFF_VIOLATION"):
        _assert_causal_cutoff(
            target_draw_number="115000080",
            target_draw_date="2026-08-18",
            history_cutoff_draw=cutoff_draw,
            history_cutoff_date=cutoff_date,
            history_rows=(),
        )


def test_assert_causal_cutoff_rejects_any_row_at_or_after_target() -> None:
    with pytest.raises(ValueError, match="CAUSAL_CUTOFF_VIOLATION"):
        _assert_causal_cutoff(
            target_draw_number="115000080",
            target_draw_date="2026-08-18",
            history_cutoff_draw="115000079",
            history_cutoff_date="2026-08-14",
            history_rows=(
                CausalDrawRow("115000078", "2026-08-11", (1, 2, 3, 4, 5, 6)),
                CausalDrawRow("115000080", "2026-08-18", (7, 8, 9, 10, 11, 12)),  # == target
            ),
        )


def test_assert_causal_cutoff_propagates_malformed_input_without_mislabeling_it() -> None:
    """A genuine parsing error must never be swallowed or mislabeled as a cutoff violation."""

    with pytest.raises(ValueError) as excinfo:
        _assert_causal_cutoff(
            target_draw_number="115000080",
            target_draw_date="not-a-date",
            history_cutoff_draw="115000079",
            history_cutoff_date="2026-08-14",
            history_rows=(),
        )
    assert "CAUSAL_CUTOFF_VIOLATION" not in str(excinfo.value)


# ==============================================================================
# PART 2: Wiring — the operational loop actually calls the guard
# ==============================================================================


def test_create_prediction_payload_raises_on_leaky_history_cutoff() -> None:
    leaky_history = HistorySnapshot(
        rows=(),
        cutoff_draw=TARGET_DRAW_NUMBER,
        cutoff_date=TARGET_DRAW_DATE,
        draw_count=0,
        history_sha256="0" * 64,
    )
    with pytest.raises(ValueError, match="CAUSAL_CUTOFF_VIOLATION"):
        create_prediction_payload(leaky_history)


def test_run_strategy_stream_raises_directly_on_leaky_history_row() -> None:
    """A direct call must raise, never get silently absorbed as a technical failure."""

    target = PredictionTarget(
        lottery_type="BIG_LOTTO",
        draw_number="115000080",
        draw_date="2026-08-18",
        scheduled_at="2026-08-18T20:30:00+08:00",
    )
    leaky_history = HistorySnapshot(
        rows=(CausalDrawRow("115000080", "2026-08-18", (1, 2, 3, 4, 5, 6)),),
        cutoff_draw="115000079",
        cutoff_date="2026-08-14",
        draw_count=1,
        history_sha256="0" * 64,
    )
    with pytest.raises(ValueError, match="CAUSAL_CUTOFF_VIOLATION"):
        run_strategy_stream(
            STRATEGY_STREAMS[0],
            leaky_history,
            target,
            created_at=datetime.fromisoformat("2026-08-01T00:00:00+08:00"),
            prediction_run_id="test-run-guard-001",
        )


# ==============================================================================
# PART 3: Mandatory temporal-invariance test — Dataset A vs Dataset B
# ==============================================================================


def test_temporal_invariance_load_canonical_history_ignores_future_rows(
    tmp_path: Path,
) -> None:
    """PREDICTION_A == PREDICTION_B for two databases differing only after cutoff C.

    Dataset A holds history strictly through cutoff C (220 draws).  Dataset B
    holds the identical 220 draws plus the target draw itself and 39 further
    future draws (260 draws total) -- the same underlying store a caller
    would get if it forgot to bound a query to "before the target".
    """

    all_draws = _generate_replay_draws(260)
    cutoff_index = 220
    target = all_draws[cutoff_index]

    dataset_a_draws = all_draws[:cutoff_index]  # 220 draws, all strictly < target
    dataset_b_draws = all_draws  # same 220 + target itself + 40 future draws

    db_a = _seed_causal_history_database(tmp_path / "dataset_a", dataset_a_draws)
    db_b = _seed_causal_history_database(tmp_path / "dataset_b", dataset_b_draws)

    snapshot_a = load_canonical_history(
        db_a,
        target_draw_number=target.draw_number,
        target_draw_date=target.draw_date.isoformat(),
    )
    snapshot_b = load_canonical_history(
        db_b,
        target_draw_number=target.draw_number,
        target_draw_date=target.draw_date.isoformat(),
    )

    # Non-vacuity: Dataset B's underlying store genuinely contains more rows
    # than what the causal snapshot may return -- the future rows are real.
    with open_database(
        resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(tmp_path / "dataset_b")}),
        read_only=True,
    ) as connection:
        total_rows_in_b = connection.execute("SELECT COUNT(*) FROM draws").fetchone()[0]
    assert total_rows_in_b == 260
    assert total_rows_in_b > snapshot_b.draw_count

    # The invariant: identical causal snapshot regardless of what exists after C.
    assert snapshot_a.draw_count == snapshot_b.draw_count == 220
    assert snapshot_a.rows == snapshot_b.rows
    assert snapshot_a.cutoff_draw == snapshot_b.cutoff_draw
    assert snapshot_a.history_sha256 == snapshot_b.history_sha256

    # PREDICTION_A == PREDICTION_B for the same deterministic adapter.
    prediction_a = BigLottoHorizonMinimaxDisagreementAdapter().get_bets(
        snapshot_a.rows, LotteryType.BIG_LOTTO
    )
    prediction_b = BigLottoHorizonMinimaxDisagreementAdapter().get_bets(
        snapshot_b.rows, LotteryType.BIG_LOTTO
    )
    assert prediction_a == prediction_b


def test_temporal_invariance_non_vacuity_future_rows_would_change_prediction() -> None:
    """Proves the equality above is load-bearing: the adapter really is history-sensitive."""

    draws = _generate_replay_draws(260)
    clean_rows = _causal_rows(draws[:220])
    contaminated_rows = _causal_rows(draws[:260])  # + target + 40 future draws

    adapter = BigLottoHorizonMinimaxDisagreementAdapter()
    prediction_clean = adapter.get_bets(clean_rows, LotteryType.BIG_LOTTO)
    prediction_contaminated = adapter.get_bets(contaminated_rows, LotteryType.BIG_LOTTO)

    assert prediction_clean != prediction_contaminated, (
        "non-vacuity violation: injecting 40 future draws had no effect, so the "
        "equality proven above would hold trivially even under a broken cutoff"
    )


# ==============================================================================
# PART 4: Walk-forward characterization over a bounded representative window
# ==============================================================================


def test_b649_walk_forward_characterization_uses_pre_target_history_only() -> None:
    """20 sequential targets: predict from strictly-prior history, then score."""

    total_draws_needed = 220  # 200 minimum causal history + 20 walk-forward targets
    all_draws = _generate_replay_draws(total_draws_needed)
    target_sequence = all_draws[200:220]
    assert len(target_sequence) == 20

    binding = binding_from_implementation(BigLottoHorizonMinimaxDisagreementAdapter())
    adapter = BigLottoReplayAdapter((binding,))
    controller = HistoricalReplayController(adapter)

    records: list[dict[str, object]] = []
    for idx, target in enumerate(target_sequence):
        # Step 1: history is strictly prior to the target -- construction.
        history = tuple(draw for draw in all_draws if draw.sort_key < target.sort_key)
        assert len(history) >= 200
        assert max(row.sort_key for row in history) < target.sort_key
        assert target not in history
        for future_target in target_sequence[idx + 1 :]:
            assert future_target not in history
        cutoff_draw = history[-1]

        # Step 2: materialize the prediction (target's own numbers untouched so far).
        record = controller._generate_cell(binding.strategy, target, history)  # pyright: ignore[reportPrivateUsage]
        assert record.status is ReplayCellStatus.COMPLETE
        predicted_tickets = tuple(ticket.main_numbers for ticket in record.tickets)

        # Step 3: only now read the official outcome and score it.
        best_zone1_hits = max(
            evaluate_lottery_prize(
                lottery_type=LotteryType.BIG_LOTTO,
                predicted_main_numbers=ticket.main_numbers,
                predicted_special_number=ticket.special_number,
                winning_main_numbers=target.main_numbers,
                winning_special_number=target.special_number,
            ).zone1_hits
            for ticket in record.tickets
        )

        records.append(
            {
                "TARGET_DRAW": target.draw_number,
                "TRAINING_CUTOFF_DRAW": cutoff_draw.draw_number,
                "TRAINING_ROW_COUNT": len(history),
                "PREDICTION": predicted_tickets,
                "OUTCOME": target.main_numbers,
                "MATCH_COUNT": best_zone1_hits,
            }
        )

    assert len(records) == 20
    assert records[0]["TARGET_DRAW"] == "100000201"
    assert records[0]["TRAINING_CUTOFF_DRAW"] == "100000200"
    assert records[0]["TRAINING_ROW_COUNT"] == 200
    assert records[-1]["TARGET_DRAW"] == "100000220"
    assert records[-1]["TRAINING_CUTOFF_DRAW"] == "100000219"
    assert records[-1]["TRAINING_ROW_COUNT"] == 219
    match_counts = [r["MATCH_COUNT"] for r in records]
    assert all(isinstance(count, int) and 0 <= count <= 6 for count in match_counts)


# ==============================================================================
# PART 5: Strategy selection leakage check
# ==============================================================================


def test_frontend_auto_optimize_selection_never_sees_target_or_future_draws() -> None:
    """The dynamic selector's internal train/test split stays inside supplied history."""

    draws = _generate_replay_draws(41)
    target = draws[40]
    history = tuple(draw for draw in draws if draw.sort_key < target.sort_key)
    assert len(history) == 40

    causal_rows = _causal_rows(history)
    adapter = BigLottoFrontendAutoOptimizeAdapter()
    selection = adapter._select(causal_rows)  # pyright: ignore[reportPrivateUsage]

    assert selection.test_size == 8  # min(10, floor(40 * 0.2))
    assert selection.winner in adapter.candidate_strategies
    assert len(selection.final_numbers) == 6
    assert all(1 <= n <= 49 for n in selection.final_numbers)
