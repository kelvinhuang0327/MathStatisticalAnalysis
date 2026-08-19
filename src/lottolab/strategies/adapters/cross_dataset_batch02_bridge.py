"""Catalog bridge for the Batch02 cross-dataset base-method intake.

Wraps seven already-implemented POWER_LOTTO Wave 2 first-zone strategies
(:mod:`lottolab.strategies.adapters.powerlotto_wave2`) and the existing
DAILY_539 ACB+Markov+MidFreq portfolio adapter
(:mod:`lottolab.strategies.adapters.daily539_portfolio_phase2`) in the shared
:class:`~lottolab.strategies.adapters.base.BetAdapter` /
:class:`~lottolab.strategies.adapters.base.PortfolioBetAdapter` contract so
they can be registered in the production catalog (the production loader
requires a real subclass via ``issubclass``, not just a matching method
surface). No prediction algorithm is reimplemented here; every bridge
delegates to its existing, already-tested producer.
"""

from __future__ import annotations

from typing import ClassVar

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    BetAdapter,
    CausalDrawRow,
    PortfolioBetAdapter,
)
from lottolab.strategies.adapters.daily539_portfolio_phase2 import (
    Daily539AcbMarkovMidfreq3BetAdapter,
)
from lottolab.strategies.adapters.powerlotto_wave1 import P638HistoryRow
from lottolab.strategies.adapters.powerlotto_wave2 import WAVE2_STRATEGY_BY_ID

# P638HistoryRow.second_number must be an exact int in [1..8], but every
# Wave 2 first-zone predictor below reads only `.numbers` (confirmed by
# reading each one). The shared CausalDrawRow history carries no second-zone
# data to derive a real value from, so this placeholder is structurally
# required and never influences a first-zone prediction.
_UNUSED_SECOND_NUMBER_PLACEHOLDER = 1


def _as_p638_history(history: tuple[CausalDrawRow, ...]) -> tuple[P638HistoryRow, ...]:
    return tuple(
        P638HistoryRow(
            draw=row.draw,
            date=row.date,
            numbers=row.numbers,
            second_number=_UNUSED_SECOND_NUMBER_PLACEHOLDER,
        )
        for row in history
    )


class _PowerLottoWave2BridgeAdapter(BetAdapter):
    """Shared first-zone-only bridge for one Wave 2 ``P638StrategySpec``.

    Emits ``special_number=None`` (the :class:`BetAdapter` default) rather
    than call the spec's own ``predict_tickets``/shared second-zone SSOT:
    that path needs real historical second-zone draws, which the shared
    ``CausalDrawRow`` contract deliberately does not carry, so fabricating
    one would produce a second-zone number that only looks predicted.
    First-zone-only is the faithful bridge, not a shortcut.
    """

    supported_lottery_types = (LotteryType.POWER_LOTTO,)
    _wave2_strategy_id: ClassVar[str]

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        spec = WAVE2_STRATEGY_BY_ID[self._wave2_strategy_id]
        # predict_tickets() is the spec's public entry point; it also derives
        # a second-zone number via the shared SSOT, which we deliberately
        # discard (see the class docstring) rather than call the private
        # `_predictor` field directly.
        first_zone, _second_zone = spec.predict_tickets(
            _as_p638_history(history), lottery_type
        )[0]
        return first_zone


class PowerC01RecencyDecayBridgeAdapter(_PowerLottoWave2BridgeAdapter):
    _wave2_strategy_id = "power_c01_recency_decay_1bet"
    strategy_id = _wave2_strategy_id
    strategy_name = "威力彩 指數衰減近期權重"
    strategy_version = WAVE2_STRATEGY_BY_ID[_wave2_strategy_id].strategy_version
    min_history = WAVE2_STRATEGY_BY_ID[_wave2_strategy_id].min_history


class PowerC02GapOverdueBridgeAdapter(_PowerLottoWave2BridgeAdapter):
    _wave2_strategy_id = "power_c02_gap_overdue_1bet"
    strategy_id = _wave2_strategy_id
    strategy_name = "威力彩 間隔逾期比率"
    strategy_version = WAVE2_STRATEGY_BY_ID[_wave2_strategy_id].strategy_version
    min_history = WAVE2_STRATEGY_BY_ID[_wave2_strategy_id].min_history


class PowerC03PairCentralityBridgeAdapter(_PowerLottoWave2BridgeAdapter):
    _wave2_strategy_id = "power_c03_pair_centrality_1bet"
    strategy_id = _wave2_strategy_id
    strategy_name = "威力彩 配對共現中心度"
    strategy_version = WAVE2_STRATEGY_BY_ID[_wave2_strategy_id].strategy_version
    min_history = WAVE2_STRATEGY_BY_ID[_wave2_strategy_id].min_history


class PowerC04ZoneBalancedBridgeAdapter(_PowerLottoWave2BridgeAdapter):
    _wave2_strategy_id = "power_c04_zone_balanced_1bet"
    strategy_id = _wave2_strategy_id
    strategy_name = "威力彩 分區平衡頻率"
    strategy_version = WAVE2_STRATEGY_BY_ID[_wave2_strategy_id].strategy_version
    min_history = WAVE2_STRATEGY_BY_ID[_wave2_strategy_id].min_history


class PowerC05DispersionMatchBridgeAdapter(_PowerLottoWave2BridgeAdapter):
    _wave2_strategy_id = "power_c05_dispersion_match_1bet"
    strategy_id = _wave2_strategy_id
    strategy_name = "威力彩 離散度匹配"
    strategy_version = WAVE2_STRATEGY_BY_ID[_wave2_strategy_id].strategy_version
    min_history = WAVE2_STRATEGY_BY_ID[_wave2_strategy_id].min_history


class PowerC06RegimeCusumBridgeAdapter(_PowerLottoWave2BridgeAdapter):
    _wave2_strategy_id = "power_c06_regime_cusum_1bet"
    strategy_id = _wave2_strategy_id
    strategy_name = "威力彩 CUSUM 狀態切換頻率"
    strategy_version = WAVE2_STRATEGY_BY_ID[_wave2_strategy_id].strategy_version
    min_history = WAVE2_STRATEGY_BY_ID[_wave2_strategy_id].min_history


class PowerC07BordaEnsembleBridgeAdapter(_PowerLottoWave2BridgeAdapter):
    """Reuses C01+C02+C03+C04's own rankings inside the wrapped Wave 2
    predictor; this bridge does not duplicate their algorithms."""

    _wave2_strategy_id = "power_c07_borda_ensemble_1bet"
    strategy_id = _wave2_strategy_id
    strategy_name = "威力彩 Borda 集成（C01+C02+C03+C04）"  # noqa: RUF001
    strategy_version = WAVE2_STRATEGY_BY_ID[_wave2_strategy_id].strategy_version
    min_history = WAVE2_STRATEGY_BY_ID[_wave2_strategy_id].min_history


class Daily539AcbMarkovMidfreq3BetCatalogAdapter(PortfolioBetAdapter):
    """Catalog-facing bridge for the existing ``Daily539AcbMarkovMidfreq3BetAdapter``.

    That class already implements the full producer logic against the shared
    ``CausalDrawRow`` contract but predates :class:`PortfolioBetAdapter` and
    does not subclass it; the production loader requires a real
    ``PortfolioBetAdapter`` subclass, so this bridge delegates to the
    existing class's public ``get_bets_with_emission`` rather than
    reimplementing its scoring.
    """

    strategy_id = Daily539AcbMarkovMidfreq3BetAdapter.strategy_id
    strategy_name = Daily539AcbMarkovMidfreq3BetAdapter.strategy_name
    strategy_version = Daily539AcbMarkovMidfreq3BetAdapter.strategy_version
    min_history = Daily539AcbMarkovMidfreq3BetAdapter.min_history
    native_ticket_count = Daily539AcbMarkovMidfreq3BetAdapter.native_ticket_count
    supported_lottery_types = (LotteryType.DAILY_539,)

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        executions = Daily539AcbMarkovMidfreq3BetAdapter().get_bets_with_emission(
            history, lottery_type
        )
        return tuple(execution.emitted_main_numbers for execution in executions)


__all__ = [
    "Daily539AcbMarkovMidfreq3BetCatalogAdapter",
    "PowerC01RecencyDecayBridgeAdapter",
    "PowerC02GapOverdueBridgeAdapter",
    "PowerC03PairCentralityBridgeAdapter",
    "PowerC04ZoneBalancedBridgeAdapter",
    "PowerC05DispersionMatchBridgeAdapter",
    "PowerC06RegimeCusumBridgeAdapter",
    "PowerC07BordaEnsembleBridgeAdapter",
]
