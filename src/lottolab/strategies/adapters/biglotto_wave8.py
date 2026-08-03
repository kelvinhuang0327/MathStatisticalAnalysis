"""DB-free production adapters for the frozen CES/DMS/Greedy/MWSC cluster.

The donor scripts at commit ``49a25effa62fc24f40789c16be6f11bdfb41a4a9``
couple their backtest wrappers to the legacy database.  Their prediction methods are
already preserved by the dependency-free Wave 26 native helper, so the application
composition root injects that authority into these adapters.  Ticket order and positional
duplicates pass through unchanged.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter

CES_METHOD_ID = "tools/test_ces.py"
DMS_METHOD_ID = "tools/test_dms.py"
GREEDY_METHOD_ID = "tools/test_greedy_optimizer.py"
MWSC_METHOD_ID = "tools/test_mwsc.py"

Wave26PortfolioAuthority = Callable[
    [str, str, tuple[CausalDrawRow, ...]],
    tuple[tuple[int, ...], ...],
]


def _target_after_causal_cutoff(history: tuple[CausalDrawRow, ...]) -> str:
    """Return a deterministic request identity absent from the causal history."""

    draw_ids = {row.draw for row in history}
    target = f"{history[-1].draw}:lottolab-next-target"
    while target in draw_ids:
        target = f"{target}:next"
    return target


class _BigLottoWave8PortfolioAdapter(PortfolioBetAdapter):
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 3
    requires_wave26_authority: ClassVar[bool] = True
    legacy_method_id: ClassVar[str]

    def __init__(self, *, wave26_authority: Wave26PortfolioAuthority) -> None:
        self._wave26_authority = wave26_authority

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return self._wave26_authority(
            self.legacy_method_id,
            _target_after_causal_cutoff(history),
            history,
        )


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
