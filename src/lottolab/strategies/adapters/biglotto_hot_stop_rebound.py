"""Target-native port of the frozen Hot-Stop Rebound parameter grid.

The donor is ``tools/backtest_biglotto_hot_stop_rebound.py`` at legacy
commit ``49a25effa62fc24f40789c16be6f11bdfb41a4a9`` (recorded blob
``b3758b5c855fe42bae5d9a9de5b66b8079755ba7``, SHA-256
``1794a8c507aed174efe13310a3a3b7774158149931ce70101a2cfb729d54b2f5``).
Its complete retained source-equivalent reference is
``lottolab.application.legacy_source_native_portfolios_wave6``.

The target edge supplies oldest-first causal rows. The donor counts each
number in the trailing 100 draws, measures its current gap after a trailing
10-draw appearance gate, and emits one ticket for each of eight preserved
frequency/gap threshold pairs. Positional duplicates across configurations
are source-native and remain intact. The selector is deterministic and does
not use the donor script's database-backed reporting entrypoint.
"""

from __future__ import annotations

from collections import Counter

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InvalidOutput,
    PortfolioBetAdapter,
)

_STRATEGY_ID = "legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae"
_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6
_MINIMUM_HISTORY = 200
_FREQUENCY_WINDOW = 100
_RECENT_GAP_WINDOW = 10
_PARAMETER_GRID = (
    (12, 8),
    (12, 10),
    (15, 8),
    (15, 10),
    (15, 12),
    (18, 8),
    (18, 10),
    (20, 10),
)


def _hot_stop_statistics(
    history: tuple[CausalDrawRow, ...],
) -> tuple[dict[int, int], dict[int, int]]:
    recent_frequency = history[-_FREQUENCY_WINDOW:]
    frequency = Counter(
        number for row in recent_frequency for number in row.numbers
    )
    appeared_in_recent = {
        number
        for row in history[-_RECENT_GAP_WINDOW:]
        for number in row.numbers
    }
    gaps: dict[int, int] = {}
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        if number in appeared_in_recent:
            gaps[number] = 0
            continue
        gap = 0
        for row in reversed(history):
            if number in row.numbers:
                break
            gap += 1
        gaps[number] = gap
    frequencies = {
        number: frequency.get(number, 0)
        for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
    }
    return frequencies, gaps


def _hot_stop_ticket(
    *,
    frequencies: dict[int, int],
    gaps: dict[int, int],
    frequency_threshold: int,
    gap_threshold: int,
) -> tuple[int, ...]:
    candidates = [
        (number, frequencies[number] * gaps[number])
        for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
        if frequencies[number] >= frequency_threshold
        and gaps[number] >= gap_threshold
    ]
    candidates.sort(key=lambda item: -item[1])
    selected = [number for number, _score in candidates[:_PICK_COUNT]]
    if len(selected) < _PICK_COUNT:
        used = set(selected)
        frequency_ranked = sorted(
            range(_MIN_NUMBER, _MAX_NUMBER + 1),
            key=lambda number: -frequencies[number],
        )
        for number in frequency_ranked:
            if number not in used:
                selected.append(number)
                if len(selected) >= _PICK_COUNT:
                    break
    return tuple(sorted(selected[:_PICK_COUNT]))


def _hot_stop_rebound_tickets(
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], ...]:
    frequencies, gaps = _hot_stop_statistics(history)
    return tuple(
        _hot_stop_ticket(
            frequencies=frequencies,
            gaps=gaps,
            frequency_threshold=frequency_threshold,
            gap_threshold=gap_threshold,
        )
        for frequency_threshold, gap_threshold in _PARAMETER_GRID
    )


class BigLottoHotStopReboundAdapter(PortfolioBetAdapter):
    """Deterministic eight-position hot-frequency/gap-threshold portfolio."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Hot-Stop Rebound 熱號休停 8組態"
    strategy_version = "v0.1"
    min_history = _MINIMUM_HISTORY
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = len(_PARAMETER_GRID)

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
        return _hot_stop_rebound_tickets(history)


__all__ = ["BigLottoHotStopReboundAdapter"]
