"""Replay adapter for the audited Wave 27 two-bet optimizer."""

from typing import cast

from lottolab.application.legacy_history_native_portfolios import LegacyHistoryDraw
from lottolab.application.legacy_source_native_portfolios_wave27 import (
    MODEL_V1_METHOD_ID,
    LegacySourceNativeWave27Request,
    generate_legacy_source_native_wave27_portfolio,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter


class FrozenTwoBetOptimizer(PortfolioBetAdapter):
    strategy_id = "legacy_biglotto__biglotto_2bet_optimizer__898ac9e38876"
    strategy_version = "legacy-source-49a25effa62f-898ac9e38876"
    strategy_name = "大樂透 雙注覆蓋優化"
    min_history = 1
    native_ticket_count = 2
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict_all(
        self, history: tuple[CausalDrawRow, ...], lottery_type: LotteryType
    ) -> tuple[Ticket, ...]:
        # Wave 27 uses the target label only for audit metadata. Its statistical
        # predictor seeds from the causal history length.
        request = LegacySourceNativeWave27Request(
            legacy_method_id=MODEL_V1_METHOD_ID,
            target_draw_number=f"AFTER_{history[-1].draw}",
            history=tuple(
                LegacyHistoryDraw(row.draw, cast(Ticket, row.numbers)) for row in history
            ),
        )
        return generate_legacy_source_native_wave27_portfolio(request).tickets
