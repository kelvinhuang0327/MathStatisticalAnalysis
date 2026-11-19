"""Historical Wave 58 tickets from EnhancedDualBetPredictor.predict('BIG_LOTTO')."""

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    BetAdapterExecution,
    CausalDrawRow,
    InsufficientHistory,
    PortfolioBetAdapter,
)
from lottolab.strategies.adapters.biglotto_wave10 import (
    _bayesian_desc_ticket,
    _filter_prediction,
    _negative_selection_excluded,
    _zone_balance_ticket,
)


class FrozenEnhancedDualBetPredictor(PortfolioBetAdapter):
    strategy_id = "legacy_biglotto__enhanced_dual_bet_predictor__d5b3de348d01"
    strategy_version = "legacy-source-49a25effa62f-d5b3de348d01"
    strategy_name = "大樂透增強型雙注預測"
    min_history = 100
    native_ticket_count = 2
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def get_bets_with_emission(
        self, history: object, lottery_type: LotteryType
    ) -> tuple[BetAdapterExecution, ...]:
        try:
            return super().get_bets_with_emission(history, lottery_type)
        except InsufficientHistory as exc:
            raise InsufficientHistory("AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM") from exc

    def _predict_all(
        self, history: tuple[CausalDrawRow, ...], lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], ...]:
        recent_first = history[::-1]
        excluded = _negative_selection_excluded(recent_first)
        # Zone balance applies the donor's own draw-ID ordering guard.
        zone = sorted(_zone_balance_ticket(recent_first[:500]))
        # This helper takes chronological rows and scores the oldest 20 of the 300,
        # reproducing history[-20:] inside the donor's newest-first Bayesian call.
        bayesian = sorted(_bayesian_desc_ticket(history[-300:]))
        return tuple(
            tuple(_filter_prediction(bet, excluded, recent_first) if excluded else bet)
            for bet in (zone, bayesian)
        )
