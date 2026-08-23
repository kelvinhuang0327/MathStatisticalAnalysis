"""Public API for internal, DB-free strategy adapters."""

from lottolab.strategies.adapters.base import (
    BetAdapter,
    BetAdapterError,
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    PortfolioBetAdapter,
    RejectPrediction,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_frontend_markov import (
    BigLottoFrontendMarkovAdapter,
)
from lottolab.strategies.adapters.biglotto_frontend_trend import (
    BigLottoFrontendTrendAdapter,
)
from lottolab.strategies.adapters.biglotto_orthogonal_2bet import (
    BigLottoOrthogonal2BetAdapter,
)
from lottolab.strategies.adapters.biglotto_selected import (
    BigLottoDeviation2BetAdapter,
    BigLottoDeviation2BetBet2Adapter,
    BigLottoP02BetBet1Adapter,
    BigLottoP02BetBet2Adapter,
    BigLottoSocialWisdomAntiPopularityAdapter,
    BigLottoZoneSplit3BetBet1Adapter,
    BigLottoZoneSplit3BetBet2Adapter,
    BigLottoZoneSplit3BetBet3Adapter,
)
from lottolab.strategies.adapters.biglotto_wave1 import (
    BigLottoDynamicFrequencyAdapter,
    BigLottoEchoPhase2Adapter,
    BigLottoGraphPredictorAdapter,
    BigLottoHotCooccurrenceAdapter,
    BigLottoMustHitTop6Adapter,
)

__all__ = [
    "BetAdapter",
    "BetAdapterError",
    "BigLottoDeviation2BetAdapter",
    "BigLottoDeviation2BetBet2Adapter",
    "BigLottoDynamicFrequencyAdapter",
    "BigLottoEchoPhase2Adapter",
    "BigLottoFrontendMarkovAdapter",
    "BigLottoFrontendTrendAdapter",
    "BigLottoGraphPredictorAdapter",
    "BigLottoHotCooccurrenceAdapter",
    "BigLottoMustHitTop6Adapter",
    "BigLottoOrthogonal2BetAdapter",
    "BigLottoP02BetBet1Adapter",
    "BigLottoP02BetBet2Adapter",
    "BigLottoSocialWisdomAntiPopularityAdapter",
    "BigLottoZoneSplit3BetBet1Adapter",
    "BigLottoZoneSplit3BetBet2Adapter",
    "BigLottoZoneSplit3BetBet3Adapter",
    "CausalDrawRow",
    "InsufficientHistory",
    "InvalidOutput",
    "PortfolioBetAdapter",
    "RejectPrediction",
    "UnsupportedLotteryType",
]
