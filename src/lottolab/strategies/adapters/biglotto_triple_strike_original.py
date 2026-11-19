"""Replay the original BIG_LOTTO Triple Strike three-ticket portfolio."""

from __future__ import annotations

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters import biglotto_quad_strike as quad
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter


class BigLottoTripleStrikeOriginalReplayAdapter(PortfolioBetAdapter):
    """The frozen backtest shares Quad Strike's first three pure selectors."""

    strategy_id = "legacy_biglotto__backtest_biglotto_triple_strike_original__4a8297a758b9"
    strategy_version = "legacy-source-49a25effa62f-4a8297a758b9"
    strategy_name = "大樂透 Triple Strike Original"
    min_history = 500
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 3

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        fourier = quad._fourier_rhythm_ticket(history)  # pyright: ignore[reportPrivateUsage]
        used = frozenset(fourier)
        cold = quad._cold_numbers_ticket(history, used)  # pyright: ignore[reportPrivateUsage]
        tail = quad._tail_balance_ticket(history, used.union(cold))  # pyright: ignore[reportPrivateUsage]
        return fourier, cold, tail
