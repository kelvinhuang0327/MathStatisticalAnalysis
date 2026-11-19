"""Inventory identities for the isolated-prefix BIG_LOTTO K10 replay.

These declarations identify retained historical results. They are not
prediction adapters and do not claim an executable Replay binding.
"""

from lottolab.domain.draws import LotteryType


class LegacyK10CausalHistoryIdentity:
    """Identify the new prefix-isolated Legacy historical replay."""

    strategy_id = "legacy_biglotto__evolution_engine__3df019c31ce4"
    strategy_version = "v0.5-prefix-isolated-r1"
    strategy_name = "Legacy K10 isolated-prefix historical replay"
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    status = "HISTORICAL_PREFIX_VERIFIED"


class H1K10CausalHistoryIdentity:
    """Identify the new prefix-isolated H1 historical replay."""

    strategy_id = "tasklocal_evolution_h1_duplicate_completion_20261105"
    strategy_version = "h1-prefix-isolated-r1"
    strategy_name = "H1 K10 isolated-prefix historical replay"
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    status = "HISTORICAL_PREFIX_VERIFIED"


class H2K10CausalHistoryIdentity:
    """Identify the fixed-seed H2 K10 historical replay."""

    strategy_id = "tasklocal_evolution_h2_uniform_cover_20261105"
    strategy_version = "h2-prefix-isolated-r1"
    strategy_name = "H2 K10 fixed-seed historical replay"
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    status = "HISTORICAL_FIXED_SEED"
