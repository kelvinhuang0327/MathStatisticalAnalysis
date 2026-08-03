"""DB-free production adapters for the frozen CES/DMS/Greedy/MWSC cluster.

The donor scripts at commit ``49a25effa62fc24f40789c16be6f11bdfb41a4a9``
couple their backtest wrappers to the legacy database.  Their prediction methods are
already preserved by the dependency-free Wave 26 native helper, so these adapters only
translate validated causal rows into that helper's request contract.  Ticket order and
positional duplicates pass through unchanged.
"""

from __future__ import annotations

from typing import ClassVar, cast

from lottolab.application.legacy_history_native_portfolios import LegacyHistoryDraw
from lottolab.application.legacy_source_native_portfolios_wave26 import (
    CES_METHOD_ID,
    DMS_METHOD_ID,
    GREEDY_METHOD_ID,
    MWSC_METHOD_ID,
    LegacySourceNativeWave26Request,
    generate_legacy_source_native_wave26_portfolio,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter


def _target_after_causal_cutoff(history: tuple[CausalDrawRow, ...]) -> str:
    """Return a deterministic request identity absent from the causal history."""

    draw_ids = {row.draw for row in history}
    target = f"{history[-1].draw}:lottolab-next-target"
    while target in draw_ids:
        target = f"{target}:next"
    return target


def _generate_frozen_portfolio(
    method_id: str,
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], ...]:
    legacy_history = tuple(
        LegacyHistoryDraw(draw_number=row.draw, numbers=cast(Ticket, row.numbers))
        for row in history
    )
    return generate_legacy_source_native_wave26_portfolio(
        LegacySourceNativeWave26Request(
            legacy_method_id=method_id,
            target_draw_number=_target_after_causal_cutoff(history),
            history=legacy_history,
        )
    ).tickets


class _BigLottoWave8PortfolioAdapter(PortfolioBetAdapter):
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 3
    legacy_method_id: ClassVar[str]

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _generate_frozen_portfolio(self.legacy_method_id, history)


class BigLottoCesThreeAdapter(_BigLottoWave8PortfolioAdapter):
    """Three constrained, score-sorted CES tickets in donor order."""

    strategy_id = "legacy_biglotto__test_ces__78d17c530ab8"
    strategy_name = "大樂透 CES 約束菁英取樣三注"
    strategy_version = "v0.1"
    legacy_method_id = CES_METHOD_ID


class BigLottoDmsThreeAdapter(_BigLottoWave8PortfolioAdapter):
    """Three DMS-selected Unified method tickets in donor order."""

    strategy_id = "legacy_biglotto__test_dms__b63442289bd5"
    strategy_name = "大樂透 DMS 動態方法選擇三注"
    strategy_version = "v0.1"
    min_history = 20
    legacy_method_id = DMS_METHOD_ID


class BigLottoGreedyThreeAdapter(_BigLottoWave8PortfolioAdapter):
    """Three diversity-greedy constrained tickets in donor order."""

    strategy_id = "legacy_biglotto__test_greedy_optimizer__82df7f878ece"
    strategy_name = "大樂透 Greedy 約束最佳化三注"
    strategy_version = "v0.1"
    legacy_method_id = GREEDY_METHOD_ID


class BigLottoMwscThreeAdapter(_BigLottoWave8PortfolioAdapter):
    """Three multi-window consensus slices in donor order."""

    strategy_id = "legacy_biglotto__test_mwsc__ba37643d6a3b"
    strategy_name = "大樂透 MWSC 多視窗共識三注"
    strategy_version = "v0.1"
    legacy_method_id = MWSC_METHOD_ID


__all__ = [
    "BigLottoCesThreeAdapter",
    "BigLottoDmsThreeAdapter",
    "BigLottoGreedyThreeAdapter",
    "BigLottoMwscThreeAdapter",
]
