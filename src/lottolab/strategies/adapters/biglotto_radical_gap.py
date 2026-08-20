"""Target-native port of the frozen Radical Gap backtest portfolio.

The donor is ``tools/backtest_radical_strategy.py`` at legacy commit
``49a25effa62fc24f40789c16be6f11bdfb41a4a9`` (recorded blob
``c460fb65561000a1e3a0d5558133784603860f2c``, SHA-256
``e54cc0812bc6fff14a259282a37821810d264c023c4fb87517305b511db08fd9``).
Its complete retained reference is
``lottolab.application.legacy_source_native_portfolios_wave31``.

The target edge supplies oldest-first causal rows. The donor uses the latest
300 rows newest-first, combines Unified deviation, adaptive Markov, and
frequency tickets with weights 1.5, 1.2, and 1.0, and emits two positional
tickets after excluding 1-19 and then 20-29. Component failures are skipped;
an undersized candidate pool closes explicitly instead of being filled.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InvalidOutput,
    PortfolioBetAdapter,
)
from lottolab.strategies.adapters.biglotto_wave3 import (
    _unified_deviation_ticket,
    _unified_frequency_ticket,
)
from lottolab.strategies.adapters.biglotto_wave6 import _frozen_markov_ticket

_STRATEGY_ID = "legacy_biglotto__backtest_radical_strategy__e54cc0812bc6"
_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6
_MINIMUM_HISTORY = 50
_SOURCE_HISTORY_LIMIT = 300
_CANDIDATE_POOL_LIMIT = 12
_GAP_EXCLUSION_RANGES = ((1, 19), (20, 29))
_ENGINE_WEIGHTS = (
    ("deviation", 1.5),
    ("markov", 1.2),
    ("frequency", 1.0),
)


def _engine_ticket(
    method_name: str,
    source_history: tuple[CausalDrawRow, ...],
) -> tuple[int, ...]:
    if method_name == "deviation":
        return _unified_deviation_ticket(source_history)
    if method_name == "markov":
        return _frozen_markov_ticket(source_history)
    if method_name == "frequency":
        return _unified_frequency_ticket(source_history)
    raise InvalidOutput(f"{_STRATEGY_ID}: unknown frozen Unified method")


def _weighted_candidates(
    source_history: tuple[CausalDrawRow, ...],
    exclude_range: range,
) -> tuple[int, ...]:
    candidates: dict[int, float] = {}
    for method_name, weight in _ENGINE_WEIGHTS:
        try:
            result = _engine_ticket(method_name, source_history)
        except Exception:  # The donor skips each failed component.
            continue
        for index, number in enumerate(result):
            if number not in exclude_range:
                candidates[number] = (
                    candidates.get(number, 0.0) + (20 - index) * weight
                )
    ranked = sorted(
        candidates,
        key=lambda number: candidates[number],
        reverse=True,
    )
    return tuple(ranked[:_CANDIDATE_POOL_LIMIT])


def _ticket(numbers: tuple[int, ...]) -> tuple[int, ...]:
    values = tuple(sorted(numbers))
    if (
        len(values) != _PICK_COUNT
        or len(set(values)) != _PICK_COUNT
        or any(
            type(number) is not int
            or not _MIN_NUMBER <= number <= _MAX_NUMBER
            for number in values
        )
    ):
        raise InvalidOutput(
            f"{_STRATEGY_ID}: frozen donor emitted fewer than six legal candidates"
        )
    return values


def _radical_gap_tickets(
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    source_history = tuple(reversed(history))[:_SOURCE_HISTORY_LIMIT]
    candidate_pools = tuple(
        _weighted_candidates(
            source_history,
            range(start, end + 1),
        )
        for start, end in _GAP_EXCLUSION_RANGES
    )
    first, second = (
        _ticket(pool[:_PICK_COUNT]) for pool in candidate_pools
    )
    return first, second


class BigLottoRadicalGapBacktestAdapter(PortfolioBetAdapter):
    """Deterministic two-ticket portfolio with complementary gap exclusions."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Radical Gap 雙區排除 2注"
    strategy_version = "v0.1"
    min_history = _MINIMUM_HISTORY
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        del lottery_type
        if len({row.draw for row in history}) != len(history):
            raise InvalidOutput(
                f"{self.strategy_id}: causal draw identities must be unique"
            )
        return _radical_gap_tickets(history)


__all__ = ["BigLottoRadicalGapBacktestAdapter"]
