"""BigLotto native-strategy wave 5 ports from the frozen legacy catalog.

The five adapters in this module preserve the deterministic number-selection
logic at donor commit ``49a25effa62fc24f40789c16be6f11bdfb41a4a9`` while
removing only the source scripts' database, console, and file-output shells.
Their native portfolio order and positional duplicates are intentionally left
unchanged.  Shared UnifiedPredictionEngine and echo helpers are reused from
the already parity-verified wave 1, 3, and 4 strategy-layer ports; importing
the separate research application ports would violate the repository's
``strategies`` dependency boundary.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from collections import Counter
from itertools import combinations

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter
from lottolab.strategies.adapters.biglotto_wave1 import (
    _continuous_temperature,
    _echo_detector,
)
from lottolab.strategies.adapters.biglotto_wave3 import (
    _unified_deviation_ticket,
    _unified_frequency_ticket,
    _unified_markov_ticket,
    _unified_statistical_ticket,
)
from lottolab.strategies.adapters.biglotto_wave4 import _unified_zone_balance_ticket

_MIN_NUM = 1
_MAX_NUM = 49
_PICK = 6
_CLUSTER_WINDOW = 150


def _cluster_cooccurrence(
    history: tuple[CausalDrawRow, ...],
) -> Counter[tuple[int, int]]:
    cooccurrence: Counter[tuple[int, int]] = Counter()
    for draw in history:
        for pair in combinations(sorted(draw.numbers), 2):
            cooccurrence[pair] += 1
    return cooccurrence


def _cluster_centers(
    cooccurrence: Counter[tuple[int, int]],
    *,
    top_k: int,
) -> list[int]:
    scores: Counter[int] = Counter()
    for (left, right), count in cooccurrence.items():
        scores[left] += count
        scores[right] += count
    return [number for number, _count in scores.most_common(top_k)]


def _cluster_expand(
    anchor: int,
    cooccurrence: Counter[tuple[int, int]],
    *,
    exclude: set[int],
) -> tuple[int, ...]:
    candidates: Counter[int] = Counter()
    for (left, right), count in cooccurrence.items():
        if left == anchor and right not in exclude:
            candidates[right] += count
        elif right == anchor and left not in exclude:
            candidates[left] += count

    selected = [anchor]
    for number, _count in candidates.most_common(12):
        if number not in selected and number not in exclude:
            selected.append(number)
        if len(selected) >= _PICK:
            break

    if len(selected) < _PICK:
        all_numbers: Counter[int] = Counter()
        for left, right in cooccurrence:
            all_numbers[left] += 1
            all_numbers[right] += 1
        for number, _count in all_numbers.most_common(50):
            if number not in selected and number not in exclude:
                selected.append(number)
            if len(selected) >= _PICK:
                break
    return tuple(sorted(selected[:_PICK]))


def _cluster_portfolio(
    history: tuple[CausalDrawRow, ...],
    *,
    native_ticket_count: int,
) -> tuple[tuple[int, ...], ...]:
    # DatabaseManager returned recent-first rows in both frozen scripts.
    source_history = tuple(reversed(history))[:_CLUSTER_WINDOW]
    cooccurrence = _cluster_cooccurrence(source_history)
    centers = _cluster_centers(cooccurrence, top_k=native_ticket_count + 2)
    bets: list[tuple[int, ...]] = []
    for index in range(native_ticket_count):
        if index >= len(centers):
            break
        exclude = {number for previous in bets for number in previous[:2]}
        candidate = _cluster_expand(
            centers[index],
            cooccurrence,
            exclude=exclude,
        )
        if any(set(previous) == set(candidate) for previous in bets):
            continue
        bets.append(candidate)
    return tuple(bets)


class BigLottoSixBetClusterAdapter(PortfolioBetAdapter):
    """Six Cluster-Pivot tickets in frozen center-loop order."""

    strategy_id = "legacy_biglotto__predict_biglotto_6bets_cluster__1fd9e8a7ae2a"
    strategy_name = "大樂透 Cluster Pivot 6注"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 6

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _cluster_portfolio(history, native_ticket_count=self.native_ticket_count)


class BigLottoSevenBetClusterAdapter(PortfolioBetAdapter):
    """Seven Cluster-Pivot tickets in frozen center-loop order."""

    strategy_id = "legacy_biglotto__predict_biglotto_7bets_cluster__8f55b5d94669"
    strategy_name = "大樂透 Cluster Pivot 7注"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 7

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _cluster_portfolio(history, native_ticket_count=self.native_ticket_count)


def _echo_two_bet_portfolio(
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    temperatures = _continuous_temperature(history, window=50)
    echoes = _echo_detector(history, max_lag=5)
    echo_weight = 0.25
    hot_scores: dict[int, float] = {}
    cold_scores: dict[int, float] = {}
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        temperature = temperatures.get(number, 0.5)
        echo = echoes.get(number, 0.0)
        hot_scores[number] = temperature * (1 - echo_weight) + echo * echo_weight
        cold_scores[number] = (1 - temperature) * (1 - echo_weight) + echo * echo_weight
    hot_ranked = sorted(hot_scores, key=lambda number: hot_scores[number], reverse=True)
    cold_ranked = sorted(cold_scores, key=lambda number: cold_scores[number], reverse=True)
    bet1 = tuple(sorted(hot_ranked[:_PICK]))
    used = set(bet1)
    bet2 = tuple(sorted([number for number in cold_ranked if number not in used][:_PICK]))
    return bet1, bet2


class BigLottoEchoTwoBetAdapter(PortfolioBetAdapter):
    """Frozen fixed-weight Hot+Echo then disjoint Cold+Echo portfolio."""

    strategy_id = "legacy_biglotto__predict_biglotto_echo_2bet__59c20b25b1fa"
    strategy_name = "大樂透 Echo-Aware 偏差互補 2注"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _echo_two_bet_portfolio(history)


def _elite_engine_ticket(
    method_name: str,
    source_history: tuple[CausalDrawRow, ...],
) -> tuple[int, ...]:
    if method_name == "markov":
        # The donor normalized its recent-first database slice before Markov.
        return _unified_markov_ticket(tuple(reversed(source_history)))
    if method_name == "deviation":
        return _unified_deviation_ticket(source_history)
    if method_name == "statistical":
        return _unified_statistical_ticket(source_history)
    raise ValueError("unknown frozen Elite7 method")


def _elite_seven_portfolio(
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], ...]:
    source_history = tuple(reversed(history))
    rows: list[tuple[int, ...]] = []
    for method_name, window in (
        ("markov", 50),
        ("markov", 100),
        ("deviation", 100),
        ("deviation", 200),
        ("statistical", 100),
        ("statistical", 110),
    ):
        try:
            rows.append(_elite_engine_ticket(method_name, source_history[-window:]))
        except Exception:  # Frozen source skips each failed method.
            continue
    if rows:
        consensus = Counter(number for row in rows for number in row).most_common(_PICK)
        rows.append(tuple(sorted(number for number, _count in consensus)))
    return tuple(rows)


class BigLottoEliteSevenAdapter(PortfolioBetAdapter):
    """Six windowed Unified tickets followed by their consensus ticket."""

    strategy_id = "legacy_biglotto__predict_biglotto_elite7__eb46a9856446"
    strategy_name = "大樂透 Elite-7 優化預測"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 7

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _elite_seven_portfolio(history)


def _variant_statistical_ticket(
    history: tuple[CausalDrawRow, ...],
) -> tuple[int, ...]:
    try:
        return _unified_statistical_ticket(history)
    except ValueError as exc:
        if str(exc) != "FROZEN_STATISTICAL_FREQUENCY_FALLBACK_REQUIRED":
            raise
        return _unified_frequency_ticket(history)


def _variant_markov_ticket(
    history: tuple[CausalDrawRow, ...],
) -> tuple[int, ...]:
    # Preserve the donor's exact text draw-id ordering guard.  Although the
    # framework supplies causal history oldest-first, unpadded identifiers can
    # compare lexicographically descending (for example, "97" > "146").
    markov_history = history
    if len(history) > 1 and history[0].draw > history[-1].draw:
        markov_history = tuple(reversed(history))
    return _unified_markov_ticket(markov_history)


def _variant_history_portfolio(
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], ...]:
    rows: list[tuple[int, ...]] = []
    for method_name, window in (
        ("deviation", 50),
        ("deviation", 100),
        ("deviation", 200),
        ("statistical", 50),
        ("statistical", 100),
        ("statistical", 200),
        ("markov", 50),
        ("markov", 100),
        ("markov", 200),
        ("frequency", 50),
        ("zone_balance", 100),
    ):
        variant_history = history[-window:]
        if method_name == "deviation":
            ticket = _unified_deviation_ticket(variant_history)
        elif method_name == "statistical":
            ticket = _variant_statistical_ticket(variant_history)
        elif method_name == "markov":
            ticket = _variant_markov_ticket(variant_history)
        elif method_name == "frequency":
            ticket = _unified_frequency_ticket(variant_history)
        else:
            ticket = _unified_zone_balance_ticket(variant_history)
        rows.append(ticket)
    return tuple(rows)


class BigLottoVariantHistoryAdapter(PortfolioBetAdapter):
    """Eleven fixed Unified-method/window variants in declaration order."""

    strategy_id = "legacy_biglotto__research_variant_history__149648f9fffc"
    strategy_name = "大樂透歷史窗口 11 變體研究組合"
    strategy_version = "v0.1"
    min_history = 20
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 11

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _variant_history_portfolio(history)


__all__ = [
    "BigLottoEchoTwoBetAdapter",
    "BigLottoEliteSevenAdapter",
    "BigLottoSevenBetClusterAdapter",
    "BigLottoSixBetClusterAdapter",
    "BigLottoVariantHistoryAdapter",
]
