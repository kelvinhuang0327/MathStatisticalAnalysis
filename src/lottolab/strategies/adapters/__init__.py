"""Public API for internal, DB-free strategy adapters."""

from lottolab.strategies.adapters.base import (
    BetAdapter,
    BetAdapterError,
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    RejectPrediction,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_selected import (
    BigLottoSocialWisdomAntiPopularityAdapter,
    BigLottoZoneSplit3BetBet1Adapter,
)

__all__ = [
    "BetAdapter",
    "BetAdapterError",
    "BigLottoSocialWisdomAntiPopularityAdapter",
    "BigLottoZoneSplit3BetBet1Adapter",
    "CausalDrawRow",
    "InsufficientHistory",
    "InvalidOutput",
    "RejectPrediction",
    "UnsupportedLotteryType",
]
