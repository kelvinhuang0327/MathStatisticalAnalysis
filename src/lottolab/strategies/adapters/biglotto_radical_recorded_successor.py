"""Outcome-informed radical rule, restricted to after its recorded source date.

The frozen rule remains available as historical evidence under its old identity.
This successor has a new identity and refuses targets on or before the earliest
recorded Git introduction date. The Git timestamp is evidence, not proof of
the full design lineage; this successor does not claim a predictive advantage.
"""

from __future__ import annotations

from datetime import date
from typing import cast

from lottolab.application.legacy_history_native_portfolios import LegacyHistoryDraw
from lottolab.application.legacy_source_native_portfolios_wave31 import (
    RADICAL_PREDICT_METHOD_ID,
    LegacySourceNativeWave31Request,
    generate_legacy_source_native_wave31_portfolio,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayDraw, ReplayTicket
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow, RejectPrediction

RECORDED_DESIGN_DATE = date(2026, 2, 24)


class BigLottoRecordedRadicalSuccessor(BetAdapter):
    strategy_id = "research_biglotto__radical_recorded_causal_successor_v1"
    strategy_name = "大樂透 Radical 已記錄日期後單注"
    strategy_version = "v1"
    min_history = 1
    native_ticket_count = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    @staticmethod
    def _ticket(history: tuple[CausalDrawRow, ...], target_number: str) -> tuple[int, ...]:
        request = LegacySourceNativeWave31Request(
            legacy_method_id=RADICAL_PREDICT_METHOD_ID,
            target_draw_number=target_number,
            history=tuple(
                LegacyHistoryDraw(row.draw, cast(Ticket, row.numbers)) for row in history
            ),
        )
        return generate_legacy_source_native_wave31_portfolio(request).tickets[0]

    def _predict(
        self, history: tuple[CausalDrawRow, ...], lottery_type: LotteryType
    ) -> tuple[int, ...]:
        del lottery_type
        if date.fromisoformat(history[-1].date) <= RECORDED_DESIGN_DATE:
            raise RejectPrediction("design availability is not established for this history")
        return self._ticket(history, "0")

    def get_replay_tickets(
        self, history: tuple[ReplayDraw, ...], target: ReplayDraw
    ) -> tuple[ReplayTicket, ...]:
        if target.draw_date <= RECORDED_DESIGN_DATE:
            raise RejectPrediction("target precedes recorded design availability")
        if target.main_numbers != (0,) or target.special_number is not None:
            raise RejectPrediction("target outcome must be redacted before prediction")
        if not history or any(d.lottery_type is not LotteryType.BIG_LOTTO for d in history):
            raise RejectPrediction("invalid historical source")
        keys = tuple(d.sort_key for d in history)
        if keys != tuple(sorted(keys)) or len(set(keys)) != len(keys):
            raise RejectPrediction("history must be strictly ordered")
        if any(d.sort_key >= target.sort_key for d in history):
            raise RejectPrediction("target or future draw in prediction history")
        rows = tuple(
            CausalDrawRow(d.draw_number, d.draw_date.isoformat(), d.main_numbers) for d in history
        )
        return (ReplayTicket(1, self._ticket(rows, target.draw_number)),)
