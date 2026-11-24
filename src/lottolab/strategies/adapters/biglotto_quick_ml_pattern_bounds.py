"""Research identity for the Quick ML historical-pattern bounds candidate.

The candidate has the same scoring and ticket semantics as the existing
corrected successor, with its own identity and independent replay evidence.
It leaves the frozen v0.1 parent unchanged.
"""

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.biglotto_quickml_corrected_successor import (
    BigLottoQuickMlCorrectedSuccessorAdapter,
)


class BigLottoQuickMlPatternBoundsAdapter(BigLottoQuickMlCorrectedSuccessorAdapter):
    """Two-ticket research candidate; input history must precede the target."""

    strategy_id = "research_biglotto__quick_ml_pattern_bounds_v1"
    strategy_name = "大樂透 Quick ML 模式邊界修正版（2注）"  # noqa: RUF001
    strategy_version = "v0.1-research"
    status = "RESEARCH_CANDIDATE"
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
