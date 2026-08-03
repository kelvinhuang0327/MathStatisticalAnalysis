"""DB-free production adapters for the frozen CES/DMS/Greedy/MWSC cluster.

The donor scripts at commit ``49a25effa62fc24f40789c16be6f11bdfb41a4a9``
couple their backtest wrappers to the legacy database.  These adapters reproduce the
frozen method bodies with dependency-free strategy-layer primitives, translating
validated causal rows directly while preserving method order, constraints, ticket
order, and positional duplicates.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
from typing import ClassVar, cast

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter
from lottolab.strategies.adapters.biglotto_wave3 import (
    _unified_bayesian_ticket,
    _unified_deviation_ticket,
    _unified_frequency_ticket,
    _unified_statistical_ticket,
)
from lottolab.strategies.adapters.biglotto_wave4 import (
    _kill_numbers,
    _unified_hot_cold_mix_ticket,
    _unified_zone_balance_ticket,
)
from lottolab.strategies.adapters.biglotto_wave6 import (
    _frozen_markov_ticket,
    _unified_trend_ticket,
)

CES_METHOD_ID = "tools/test_ces.py"
DMS_METHOD_ID = "tools/test_dms.py"
GREEDY_METHOD_ID = "tools/test_greedy_optimizer.py"
MWSC_METHOD_ID = "tools/test_mwsc.py"

_ENGINE_METHOD_ORDER = (
    "frequency",
    "bayesian",
    "markov",
    "trend",
    "deviation",
    "statistical",
    "zone_balance",
    "hot_cold_mix",
)


class BigLottoWave8SourceError(ValueError):
    """A frozen Wave 8 source method cannot emit its exact portfolio."""


def _engine_output(
    method_name: str,
    history: tuple[CausalDrawRow, ...],
) -> tuple[int, ...]:
    if method_name == "frequency":
        return _unified_frequency_ticket(history)
    if method_name == "bayesian":
        return _unified_bayesian_ticket(history)
    if method_name == "markov":
        return _frozen_markov_ticket(history)
    if method_name == "trend":
        return _unified_trend_ticket(history)
    if method_name == "deviation":
        return _unified_deviation_ticket(history)
    if method_name == "statistical":
        return _unified_statistical_ticket(history)
    if method_name == "zone_balance":
        return _unified_zone_balance_ticket(history)
    if method_name == "hot_cold_mix":
        return _unified_hot_cold_mix_ticket(history)
    raise BigLottoWave8SourceError("unknown frozen Unified method")


def _frozen_kill_numbers(
    history: tuple[CausalDrawRow, ...],
) -> tuple[int, ...]:
    return tuple(_kill_numbers(history, 10))


def _weighted_pool(
    history: tuple[CausalDrawRow, ...],
    specifications: tuple[tuple[str, float], ...],
    kill_numbers: tuple[int, ...],
    limit: int,
) -> list[int]:
    scores: Counter[int] = Counter()
    for method_name, weight in specifications:
        try:
            for number in _engine_output(method_name, history):
                scores[number] += cast(int, weight)
        except Exception:
            continue
    for number in kill_numbers:
        scores[number] = -9999
    return [number for number, _score in scores.most_common(limit)]


def _ces_valid(row: tuple[int, ...]) -> bool:
    if not 110 <= sum(row) <= 190:
        return False
    differences = {right - left for left, right in combinations(sorted(row), 2)}
    if len(differences) - 5 < 6:
        return False
    odd = sum(number % 2 == 1 for number in row)
    return 2 <= odd <= 4 and max(row) - min(row) >= 25


def _ces_rows(
    history: tuple[CausalDrawRow, ...],
    kill_numbers: tuple[int, ...],
) -> list[list[int]]:
    specifications = (
        ("deviation", 1.5),
        ("markov", 1.5),
        ("statistical", 2.0),
        ("hot_cold_mix", 1.0),
    )
    pool = _weighted_pool(history, specifications, kill_numbers, 20)
    scores: Counter[int] = Counter()
    for method_name, weight in specifications:
        try:
            for number in _engine_output(method_name, history):
                scores[number] += cast(int, weight)
        except Exception:
            continue
    for number in kill_numbers:
        scores[number] = -9999
    valid = [
        (row, sum(scores[number] for number in row))
        for row in combinations(pool, 6)
        if _ces_valid(row)
    ]
    valid.sort(key=lambda item: item[1], reverse=True)
    selected: list[tuple[int, ...]] = []
    for row, _score in valid:
        if not selected or all(
            len(set(row) & set(previous)) <= 2 for previous in selected
        ):
            selected.append(row)
        if len(selected) >= 3:
            break
    while len(selected) < 3 and valid:
        selected.append(valid[len(selected)][0])
    return [sorted(row) for row in selected]


def _dms_rows(history: tuple[CausalDrawRow, ...]) -> list[list[int]]:
    if len(history) < 20:
        raise BigLottoWave8SourceError(
            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
        )
    performance: Counter[str] = Counter()
    for index in range(10, 30):
        offset = 30 - index
        actual = set(history[-offset].numbers)
        past = history[:-offset]
        for method_name in _ENGINE_METHOD_ORDER:
            try:
                output = _engine_output(method_name, past)
                performance[method_name] += len(set(output) & actual)
            except Exception:
                continue
    top_methods = tuple(
        method_name for method_name, _score in performance.most_common(3)
    )
    rows: list[list[int]] = []
    for method_name in top_methods:
        try:
            rows.append(sorted(_engine_output(method_name, history)))
        except Exception:
            continue
    while len(rows) < 3:
        rows.append(sorted(_engine_output("statistical", history)))
    return rows


def _greedy_score(
    row: tuple[int, ...],
    number_scores: Counter[int],
    matrix: defaultdict[int, Counter[int]],
) -> float:
    score = sum(number_scores.get(number, 0) for number in row)
    score += (
        sum(matrix[left][right] for left, right in combinations(sorted(row), 2))
        * 0.1
    )
    score -= abs(sum(row) - 150) / 50
    differences = {right - left for left, right in combinations(sorted(row), 2)}
    if len(differences) - 5 < 6:
        score -= 5
    odd = sum(number % 2 == 1 for number in row)
    if odd < 2 or odd > 4:
        score -= 10
    return score


def _greedy_rows(
    history: tuple[CausalDrawRow, ...],
    kill_numbers: tuple[int, ...],
) -> list[list[int]]:
    specifications = (
        ("deviation", 1.5),
        ("markov", 1.5),
        ("statistical", 2.0),
    )
    pool = _weighted_pool(history, specifications, kill_numbers, 18)
    number_scores: Counter[int] = Counter()
    for method_name, weight in specifications:
        try:
            for number in _engine_output(method_name, history):
                number_scores[number] += cast(int, weight)
        except Exception:
            continue
    for number in kill_numbers:
        number_scores[number] = -999
    matrix: defaultdict[int, Counter[int]] = defaultdict(Counter)
    for draw in history[-200:]:
        for left, right in combinations(sorted(draw.numbers), 2):
            matrix[left][right] += 1
            matrix[right][left] += 1
    top_five = set(pool[:5])
    scored = [
        (row, _greedy_score(row, number_scores, matrix))
        for row in combinations(pool, 6)
        if len(set(row) & top_five) >= 1
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    selected: list[tuple[int, ...]] = []
    for row, _score in scored:
        if not selected or all(
            len(set(row) & set(previous)) <= 3 for previous in selected
        ):
            selected.append(row)
        if len(selected) >= 3:
            break
    return [sorted(row) for row in selected]


def _mwsc_rows(history: tuple[CausalDrawRow, ...]) -> list[list[int]]:
    consensus: Counter[int] = Counter()
    for window in (10, 20, 50, 100):
        past = history[-window:]
        for method_name in ("statistical", "deviation", "markov"):
            try:
                for number in _engine_output(method_name, past):
                    consensus[number] += 1
            except Exception:
                continue
    for number in _frozen_kill_numbers(history):
        consensus[number] = -9999
    pool = [number for number, _score in consensus.most_common(18)]
    return [sorted(pool[start:end]) for start, end in ((0, 6), (4, 10), (8, 14))]


def _tickets_or_close(rows: list[list[int]]) -> tuple[tuple[int, ...], ...]:
    tickets: list[tuple[int, ...]] = []
    for row in rows:
        ticket = tuple(sorted(row))
        if (
            len(ticket) != 6
            or len(set(ticket)) != 6
            or any(not 1 <= number <= 49 for number in ticket)
        ):
            raise BigLottoWave8SourceError(
                "FROZEN_SOURCE_EMITTED_INVALID_NATIVE_TICKET"
            )
        tickets.append(ticket)
    if len(tickets) != 3:
        raise BigLottoWave8SourceError("FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED")
    return tuple(tickets)


def _generate_frozen_portfolio(
    method_id: str,
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], ...]:
    if method_id == CES_METHOD_ID:
        rows = _ces_rows(history, _frozen_kill_numbers(history))
    elif method_id == DMS_METHOD_ID:
        rows = _dms_rows(history)
    elif method_id == GREEDY_METHOD_ID:
        rows = _greedy_rows(history, _frozen_kill_numbers(history))
    elif method_id == MWSC_METHOD_ID:
        rows = _mwsc_rows(history)
    else:
        raise BigLottoWave8SourceError("unknown frozen Wave 8 method")
    return _tickets_or_close(rows)


class _BigLottoWave8PortfolioAdapter(PortfolioBetAdapter):
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 3
    legacy_method_id: ClassVar[str]

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _generate_frozen_portfolio(self.legacy_method_id, history)


class BigLottoCesThreeAdapter(_BigLottoWave8PortfolioAdapter):
    """Three constrained, score-sorted CES tickets in donor order."""

    strategy_id = "legacy_biglotto__test_ces__78d17c530ab8"
    strategy_name = "大樂透 CES 約束菁英取樣三注"
    strategy_version = "v0.1"
    legacy_method_id = CES_METHOD_ID


class BigLottoDmsThreeAdapter(_BigLottoWave8PortfolioAdapter):
    """Three DMS-selected Unified method tickets in donor order."""

    strategy_id = "legacy_biglotto__test_dms__b63442289bd5"
    strategy_name = "大樂透 DMS 動態方法選擇三注"
    strategy_version = "v0.1"
    min_history = 20
    legacy_method_id = DMS_METHOD_ID


class BigLottoGreedyThreeAdapter(_BigLottoWave8PortfolioAdapter):
    """Three diversity-greedy constrained tickets in donor order."""

    strategy_id = "legacy_biglotto__test_greedy_optimizer__82df7f878ece"
    strategy_name = "大樂透 Greedy 約束最佳化三注"
    strategy_version = "v0.1"
    legacy_method_id = GREEDY_METHOD_ID


class BigLottoMwscThreeAdapter(_BigLottoWave8PortfolioAdapter):
    """Three multi-window consensus slices in donor order."""

    strategy_id = "legacy_biglotto__test_mwsc__ba37643d6a3b"
    strategy_name = "大樂透 MWSC 多視窗共識三注"
    strategy_version = "v0.1"
    legacy_method_id = MWSC_METHOD_ID


__all__ = [
    "BigLottoCesThreeAdapter",
    "BigLottoDmsThreeAdapter",
    "BigLottoGreedyThreeAdapter",
    "BigLottoMwscThreeAdapter",
    "BigLottoWave8SourceError",
]
