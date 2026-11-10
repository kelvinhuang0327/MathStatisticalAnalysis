"""Inventory identity for the retained Geometry K30 one-swap research results.

This is an identity declaration, not a prediction adapter. The historical
portfolio source has UNKNOWN provenance and no verified Replay execution binding.
"""

from lottolab.domain.draws import LotteryType


class GeometryExactSwapHistoryIdentity:
    """Expose the exact research identity without claiming execution capability."""

    strategy_id = "research_biglotto__k30_geometry_exact_swap_history_v1"
    strategy_version = "v1"
    strategy_name = "Geometry K30 exact one-swap history"
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    status = "HISTORICAL_PROVENANCE_UNKNOWN"
