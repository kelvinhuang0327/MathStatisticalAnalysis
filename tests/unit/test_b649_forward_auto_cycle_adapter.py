"""Focused acceptance tests for the B649 shared-core composition."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from tools.b649_forward_auto_cycle_adapter import B649ForwardAutoCycleAdapter
from tools.b649_operational_prediction_loop import (
    HistorySnapshot,
    PredictionTarget,
    StrategyStream,
)

from lottolab.application.forward_auto_cycle_core import ForwardAutoCycleCore
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow


class _FakeSingleAdapter(BetAdapter):
    strategy_id = "auto_cycle_fake_single"
    strategy_name = "Auto Cycle Fake Single"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        assert history
        assert lottery_type is LotteryType.BIG_LOTTO
        return (1, 2, 3, 4, 5, 6)


class _FakeFailingAdapter(BetAdapter):
    strategy_id = "auto_cycle_fake_failure"
    strategy_name = "Auto Cycle Fake Failure"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        assert history
        assert lottery_type is LotteryType.BIG_LOTTO
        raise RuntimeError("synthetic failure")


def _target() -> PredictionTarget:
    return PredictionTarget(
        lottery_type="BIG_LOTTO",
        draw_number="115000081",
        draw_date="2026-08-18",
        scheduled_at="2026-08-18T20:30:00+08:00",
    )


def _history() -> HistorySnapshot:
    return HistorySnapshot(
        rows=tuple(
            CausalDrawRow(
                draw=str(index),
                date=f"2026-08-{(index % 9) + 1:02d}",
                numbers=(1, 2, 3, 4, 5, 6),
            )
            for index in range(1, 3)
        ),
        cutoff_draw="115000080",
        cutoff_date="2026-08-15",
        draw_count=2,
        history_sha256="2" * 64,
    )


def _stream(adapter: type[BetAdapter]) -> StrategyStream:
    return StrategyStream(
        strategy_id=adapter.strategy_id,
        strategy_version=adapter.strategy_version,
        enabled=True,
        adapter_factory=adapter,
        native_ticket_count=1,
    )


def _official(main_numbers: tuple[int, ...]) -> dict[str, object]:
    return {
        "lottery_type": "BIG_LOTTO",
        "draw_number": "115000081",
        "draw_date": "2026-08-18",
        "main_numbers": list(main_numbers),
        "special_number": 49,
        "source": "official:test",
    }


def _core(
    root: Path,
    *,
    streams: tuple[StrategyStream, ...],
    official: dict[str, object] | None,
) -> B649ForwardAutoCycleAdapter:
    return B649ForwardAutoCycleAdapter(
        root,
        database=root / "missing-database.db",
        target=_target(),
        streams=streams,
        history_builder=lambda _target: _history(),
        official_outcome_resolver=lambda _target: official,
        clock=lambda: datetime.fromisoformat("2026-08-18T19:00:00+08:00"),
    )


def test_b649_adapter_runs_new_target_then_repeats_without_duplicate_prediction(
    tmp_path: Path,
) -> None:
    adapter = _core(
        tmp_path,
        streams=(_stream(_FakeSingleAdapter),),
        official=_official((7, 8, 9, 10, 11, 12)),
    )
    first = ForwardAutoCycleCore(adapter).run()
    prediction_path = next((tmp_path / "predictions" / "115000081").rglob("*.json"))
    before = hashlib.sha256(prediction_path.read_bytes()).hexdigest()

    second = ForwardAutoCycleCore(adapter).run()

    assert len(first.created_predictions) == 1
    assert first.outcome_status == "NEW_OUTCOME"
    assert second.created_predictions == ()
    assert second.outcome_status == "IDENTICAL_OUTCOME"
    assert second.next_action == "NO_OP"
    assert hashlib.sha256(prediction_path.read_bytes()).hexdigest() == before


def test_b649_adapter_corrected_official_outcome_rescores_existing_prediction(
    tmp_path: Path,
) -> None:
    official = {"value": _official((7, 8, 9, 10, 11, 12))}
    adapter = B649ForwardAutoCycleAdapter(
        tmp_path,
        streams=(_stream(_FakeSingleAdapter),),
        database=tmp_path / "missing-database.db",
        target=_target(),
        history_builder=lambda _target: _history(),
        official_outcome_resolver=lambda _target: official["value"],
        clock=lambda: datetime.fromisoformat("2026-08-18T19:00:00+08:00"),
    )
    ForwardAutoCycleCore(adapter).run()
    official["value"] = _official((13, 14, 15, 16, 17, 18))

    corrected = ForwardAutoCycleCore(adapter).run()

    outcome = (tmp_path / "outcomes" / "115000081.json").read_text(encoding="utf-8")
    assert corrected.outcome_status == "CORRECTED_OUTCOME"
    assert corrected.rescore_results
    assert '"revision":2' in outcome
    assert '"main_numbers":[13,14,15,16,17,18]' in outcome


def test_b649_adapter_preserves_strategy_failure_isolation(tmp_path: Path) -> None:
    adapter = _core(
        tmp_path,
        streams=(_stream(_FakeFailingAdapter), _stream(_FakeSingleAdapter)),
        official=None,
    )

    result = ForwardAutoCycleCore(adapter).run()

    availability = {
        prediction["strategy_id"]: prediction["availability"]
        for prediction in result.created_predictions
    }
    assert availability == {
        "auto_cycle_fake_failure": "TECHNICAL_FAILURE",
        "auto_cycle_fake_single": "AVAILABLE",
    }
    assert result.next_action == "PREDICTIONS_CREATED_WAITING_FOR_OUTCOME"


def test_b649_default_target_resolution_uses_existing_unfinished_prediction(
    tmp_path: Path,
) -> None:
    adapter = _core(
        tmp_path,
        streams=(_stream(_FakeSingleAdapter),),
        official=None,
    )
    ForwardAutoCycleCore(adapter).run()

    resolved = B649ForwardAutoCycleAdapter(
        tmp_path,
        database=tmp_path / "missing-database.db",
        streams=(_stream(_FakeSingleAdapter),),
        history_builder=lambda _target: _history(),
    ).resolve_next_target()

    assert resolved == _target()
