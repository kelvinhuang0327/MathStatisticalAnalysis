from datetime import date

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayDraw
from lottolab.strategies.adapters.base import RejectPrediction
from lottolab.strategies.adapters.biglotto_radical_recorded_successor import (
    BigLottoRecordedRadicalSuccessor,
)


def test_successor_rejects_known_outcome_and_pre_recorded_design() -> None:
    adapter = BigLottoRecordedRadicalSuccessor()
    history = (
        ReplayDraw(LotteryType.BIG_LOTTO, "115000020", date(2026, 2, 20), (1, 2, 3, 4, 5, 6), 7),
    )
    with pytest.raises(RejectPrediction, match="precedes"):
        adapter.get_replay_tickets(
            history, ReplayDraw(LotteryType.BIG_LOTTO, "115000021", date(2026, 2, 24), (0,))
        )
    with pytest.raises(RejectPrediction, match="redacted"):
        adapter.get_replay_tickets(
            history,
            ReplayDraw(
                LotteryType.BIG_LOTTO, "115000022", date(2026, 2, 25), (1, 2, 3, 4, 5, 6), 7
            ),
        )


def test_successor_rejects_future_or_unordered_history() -> None:
    adapter = BigLottoRecordedRadicalSuccessor()
    earlier = ReplayDraw(
        LotteryType.BIG_LOTTO, "115000020", date(2026, 2, 20), (1, 2, 3, 4, 5, 6), 7
    )
    future = ReplayDraw(
        LotteryType.BIG_LOTTO, "115000023", date(2026, 2, 27), (7, 8, 9, 10, 11, 12), 13
    )
    target = ReplayDraw(LotteryType.BIG_LOTTO, "115000022", date(2026, 2, 25), (0,))
    with pytest.raises(RejectPrediction, match="future"):
        adapter.get_replay_tickets((earlier, future), target)
    with pytest.raises(RejectPrediction, match="ordered"):
        adapter.get_replay_tickets((future, earlier), target)


def test_packaged_projection_returns_raw_evaluation_count() -> None:
    from lottolab.infrastructure.biglotto_multi_ticket_record_reader import (
        PackagedB649MultiTicketRecordReader,
    )

    records = PackagedB649MultiTicketRecordReader().read().records
    available = [r for r in records if r.successful_execution_count is not None]
    assert available
    assert all(r.effective_backtest_draw_count == r.successful_execution_count for r in available)
    assert all(
        r.historical_success_rate is None for r in available if r.successful_execution_count == 0
    )
    affected = [
        r
        for r in records
        if r.strategy_id == "legacy_biglotto__predict_biglotto_radical__1f1c6e060b19"
    ]
    assert len(affected) == 128
    assert all(r.historical_success_rate is None and r.rank is None for r in affected)
    assert all(
        r.metrics_unavailable_reason == "OUTCOME_INFORMED_DESIGN_CHRONOLOGY_UNSAFE"
        for r in affected
    )
