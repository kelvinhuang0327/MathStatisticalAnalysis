"""POWER_LOTTO native-strategy batch 01: thin ports of three already-built,
already-verified first-zone portfolio producers onto the catalog-loadable
``PortfolioBetAdapter`` contract.

Sources (unchanged): ``powerlotto_wave1.py``'s ``_zonal_entropy_tickets``
(``WAVE1_STRATEGIES`` id ``zonal_entropy_2bet``) and ``powerlotto_wave2.py``'s
``_apriori_tickets`` / ``_lead_lag_tickets`` (``WAVE2_STRATEGIES`` ids
``power_apriori_2bet`` / ``power_lead_lag_2bet``). All three specs already
exist, fully implemented and provenance-documented, in
``WAVE1_STRATEGY_BY_ID``/``WAVE2_STRATEGY_BY_ID`` -- used today only by
Replay-side callers (see ``P638StrategySpec.get_bets``'s own docstring:
"Alias used by replay callers that expose adapter-style methods"). None of
the ten Wave 1/Wave 2 POWER_LOTTO specs are reachable from the production
catalog before this module: ``catalog.py`` has zero POWER_LOTTO entries.

Second-zone number: deliberately not populated (every ticket's
``special_number`` is ``None``), not silently approximated. The shared
``CausalDrawRow`` adapter contract carries only ``draw``/``date``/``numbers``
by design (see ``lottolab.strategies.adapters.base`` module docstring and
``tests/unit/test_bet_adapter_cross_dataset_contract.py``'s own
``_PowerLottoFixtureAdapter`` docstring: "a native adapter's second-zone
prediction must come from its own logic/state rather than from history rows
here"), so the real second-zone SSOT
(``lottolab.strategies.powerlotto_second_zone.second_zone_predict``) --
which requires genuine causal second-zone history -- cannot be reached from
this specific execution path without fabricating placeholder second-zone
history that would look like a real prediction. Returning ``None`` uses the
base class's own existing, already-tested extension point exactly as
designed (``_validated_special_number`` always accepts ``None``, regardless
of a lottery's ``special_number_required`` flag) rather than inventing a new
one. First-zone selection -- the actual distinguishing mechanism for all
three of these strategies -- is unaffected and preserved exactly.

``P638HistoryRow.second_number`` is filled with a fixed placeholder (``1``)
purely to satisfy that dataclass's own constructor validation; none of the
three predictor functions reused here (``_zonal_entropy_tickets``,
``_apriori_tickets``, ``_lead_lag_tickets``) ever reads ``second_number``,
only ``numbers`` -- confirmed by direct inspection of each function and its
full call graph before this port was written. No algorithm was changed,
tuned, or "improved".
"""

# pyright: reportPrivateUsage=false
# (deliberate cross-wave private-helper-import convention -- see module
# docstring: reuses already-verified Wave 1/Wave 2 predictor functions
# rather than re-deriving them)

from __future__ import annotations

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter
from lottolab.strategies.adapters.powerlotto_wave1 import (
    P638HistoryRow,
    _zonal_entropy_tickets,
)
from lottolab.strategies.adapters.powerlotto_wave2 import _apriori_tickets, _lead_lag_tickets

_PLACEHOLDER_SECOND_NUMBER = 1  # inert: never read by the first-zone-only predictors below


def _p638_history(history: tuple[CausalDrawRow, ...]) -> tuple[P638HistoryRow, ...]:
    """Reshape generic causal history into first-zone-only P638 rows.

    ``second_number`` is a required field on ``P638HistoryRow`` but is never
    consulted by any predictor this module calls (see module docstring).
    """

    return tuple(
        P638HistoryRow(
            draw=row.draw,
            date=row.date,
            numbers=row.numbers,
            second_number=_PLACEHOLDER_SECOND_NUMBER,
        )
        for row in history
    )


class PowerLottoZonalEntropy2BetAdapter(PortfolioBetAdapter):
    """Zone-entropy-gated hot/cold two-ticket portfolio (POWER_LOTTO first zone)."""

    strategy_id = "zonal_entropy_2bet"
    strategy_name = "威力彩 Zonal Entropy 2注"
    strategy_version = "v0.1-p638-wave1"
    min_history = 30
    supported_lottery_types = (LotteryType.POWER_LOTTO,)
    native_ticket_count = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _zonal_entropy_tickets(_p638_history(history))


class PowerLottoApriori2BetAdapter(PortfolioBetAdapter):
    """Top-50-pair association two-ticket portfolio (POWER_LOTTO first zone)."""

    strategy_id = "power_apriori_2bet"
    strategy_name = "威力彩 Apriori 配對關聯 2注"
    strategy_version = "v0.1-p638-wave2"
    min_history = 10
    supported_lottery_types = (LotteryType.POWER_LOTTO,)
    native_ticket_count = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _apriori_tickets(_p638_history(history))


class PowerLottoLeadLag2BetAdapter(PortfolioBetAdapter):
    """Adjacent-draw transition-matrix two-ticket portfolio (POWER_LOTTO first zone)."""

    strategy_id = "power_lead_lag_2bet"
    strategy_name = "威力彩 Lead-Lag 轉移矩陣 2注"
    strategy_version = "v0.1-p638-wave2"
    min_history = 10
    supported_lottery_types = (LotteryType.POWER_LOTTO,)
    native_ticket_count = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _lead_lag_tickets(_p638_history(history))


__all__ = [
    "PowerLottoApriori2BetAdapter",
    "PowerLottoLeadLag2BetAdapter",
    "PowerLottoZonalEntropy2BetAdapter",
]
