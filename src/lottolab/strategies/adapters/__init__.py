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
    BigLottoDeviation2BetAdapter,
    BigLottoP02BetBet1Adapter,
    BigLottoP02BetBet2Adapter,
    BigLottoSocialWisdomAntiPopularityAdapter,
    BigLottoZoneSplit3BetBet1Adapter,
    BigLottoZoneSplit3BetBet2Adapter,
)

__all__ = [
    "BetAdapter",
    "BetAdapterError",
    "BigLottoDeviation2BetAdapter",
    "BigLottoP02BetBet1Adapter",
    "BigLottoP02BetBet2Adapter",
    "BigLottoSocialWisdomAntiPopularityAdapter",
    "BigLottoZoneSplit3BetBet1Adapter",
    "BigLottoZoneSplit3BetBet2Adapter",
    "CausalDrawRow",
    "InsufficientHistory",
    "InvalidOutput",
    "RejectPrediction",
    "UnsupportedLotteryType",
]
