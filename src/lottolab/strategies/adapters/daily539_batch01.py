"""DAILY_539 native-strategy batch 01: single thin port onto the
catalog-loadable ``BetAdapter`` contract.

Source: ``src/lottolab/strategies/adapters/daily539_single_legacy.py`` --
``_acb_predict`` (``strategy_id acb_single_539``, family ``frequency_acb``).
That module's own ``Daily539AcbSingleAdapter`` already implements this exact
identity and is already used by ``tools/run_daily539_t539_wave1.py``'s
``StrategySpec`` registry, but it is a structurally duck-typed class (only a
``get_one_bet`` method) that pre-dates and does not subclass this project's
``BetAdapter`` contract, so it cannot be loaded through the production
catalog's ``ExecutableRegistry``/``GenerateOneBet`` path, which requires an
exact ``BetAdapter`` subclass. This module reuses the identical producer
function ``_acb_predict`` -- unchanged -- through a real ``BetAdapter``
subclass instead of duplicating the formula, so DAILY_539 becomes reachable
from the production catalog for the first time. No algorithm was changed,
tuned, or "improved".
"""

# pyright: reportPrivateUsage=false
# (deliberate private-helper-import: reuses daily539_single_legacy's
# already-defined producer rather than duplicating the formula -- see
# module docstring)

from __future__ import annotations

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow
from lottolab.strategies.adapters.daily539_single_legacy import _acb_predict

_MIN_HISTORY = 100  # this identity's existing min_history (== donor's _ACB_WINDOW)


class Daily539AcbSingleCatalogAdapter(BetAdapter):
    """ACB frequency-deficit + gap + zone-balance single ticket (DAILY_539)."""

    strategy_id = "acb_single_539"
    strategy_name = "今彩539 ACB Single 1注"
    strategy_version = "v0.1-p36"
    min_history = _MIN_HISTORY
    supported_lottery_types = (LotteryType.DAILY_539,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _acb_predict(history)


__all__ = ["Daily539AcbSingleCatalogAdapter"]
