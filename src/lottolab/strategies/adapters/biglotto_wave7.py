"""BigLotto native-strategy Wave 7 frozen BACKTESTED ports.

The five adapters preserve fixed single-ticket and positional portfolios from donor commit
``49a25effa62fc24f40789c16be6f11bdfb41a4a9`` without retaining the donor
scripts' database, console, or report shells.  Existing strategy-layer ports
are reused when the donor called the same frozen ``UnifiedPredictionEngine``
method; Gemini Phase 2 keeps its separate claim-verifier implementations.

Variable-count Apriori output, target-seeded methods that cannot be represented
by the current history-only adapter contract, Gemini 3-Bet's non-prefix
closures, and duplicate aliases of already-shipped strategies remain excluded.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from collections import Counter, defaultdict

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    BetAdapter,
    CausalDrawRow,
    PortfolioBetAdapter,
)
from lottolab.strategies.adapters.biglotto_wave3 import (
    _ticket,
    _unified_deviation_ticket,
    _unified_statistical_ticket,
)
from lottolab.strategies.adapters.biglotto_wave4 import (
    _unified_hot_cold_mix_ticket,
)
from lottolab.strategies.adapters.biglotto_wave6 import (
    _frozen_markov_ticket,
    _unified_trend_ticket,
)

_MIN_NUM = 1
_MAX_NUM = 49
_PICK = 6
_ATTENTION_WEIGHTS = tuple(
    (1.0 + index * 0.1) / 25.5 for index in range(15)
)
_ZONE_BALANCE_WINDOWS = (100, 200, 300, 500)


def _attention_replay_ticket(
    history: tuple[CausalDrawRow, ...],
) -> tuple[int, ...]:
    weighted_frequency: defaultdict[int, float] = defaultdict(float)
    for index, draw in enumerate(history[-15:]):
        weight = _ATTENTION_WEIGHTS[index]
        for number in draw.numbers:
            weighted_frequency[number] += weight
    ranked = sorted(
        weighted_frequency.items(),
        key=lambda item: item[1],
        reverse=True,
    )
    return _ticket([number for number, _weight in ranked[:_PICK]])


class BigLottoAttentionReplayAdapter(BetAdapter):
    """Frozen 15-draw recency-weighted frequency ticket."""

    strategy_id = (
        "legacy_biglotto__attention_replay_predictor__a811e2eb8215"
    )
    strategy_name = "大樂透 Attention Replay 15期加權頻率"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _attention_replay_ticket(history)


class BigLottoFiveMeAdapter(PortfolioBetAdapter):
    """Statistical, Deviation, Markov, Hot-Cold, then Trend tickets."""

    strategy_id = "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd"
    strategy_name = "大樂透 5ME 五方法獨立組合"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 5

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return (
            _unified_statistical_ticket(history),
            _unified_deviation_ticket(history),
            _frozen_markov_ticket(history),
            _unified_hot_cold_mix_ticket(history),
            _unified_trend_ticket(history),
        )


def _smart_true_frequency_ticket(
    history: tuple[CausalDrawRow, ...],
) -> tuple[int, ...]:
    counts: Counter[int] = Counter(
        number for draw in history[-50:] for number in draw.numbers
    )
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return _ticket([number for number, _count in ranked[:_PICK]])


class BigLottoSmartTwoBetAdapter(PortfolioBetAdapter):
    """True-Frequency-50 conservative ticket, then Deviation aggressive."""

    strategy_id = "legacy_biglotto__predict_big_lotto_smart_2bet__7acdaab1bd0a"
    strategy_name = "大樂透 Smart 2-Bet 頻率偏差互補組合"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        # The donor's database rows and both predictors are recent-first.
        return (
            _smart_true_frequency_ticket(history),
            _unified_deviation_ticket(tuple(reversed(history))),
        )


def _variance(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _dynamic_zone_partition(
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[tuple[int, ...], ...], float]:
    frequency: Counter[int] = Counter(
        number for draw in history for number in draw.numbers
    )
    sorted_pairs = sorted(
        (
            (number, frequency.get(number, 0))
            for number in range(_MIN_NUM, _MAX_NUM + 1)
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    number_of_zones = 4
    zone_size = len(sorted_pairs) // number_of_zones
    remainder = len(sorted_pairs) % number_of_zones
    zones: list[tuple[int, ...]] = []
    start_index = 0
    for index in range(number_of_zones):
        current_size = zone_size + (1 if index < remainder else 0)
        zone = tuple(
            sorted(
                number
                for number, _count in sorted_pairs[
                    start_index : start_index + current_size
                ]
            )
        )
        if zone:
            zones.append(zone)
        start_index += current_size

    zone_means = [
        sum(frequency.get(number, 0) for number in zone) / len(zone)
        for zone in zones
    ]
    between_variance = _variance(zone_means)
    within_variances = [
        _variance(
            [float(frequency.get(number, 0)) for number in zone]
        )
        for zone in zones
        if len(zone) > 1
    ]
    average_within = (
        sum(within_variances) / len(within_variances)
        if within_variances
        else 1.0
    )
    quality = between_variance / (average_within + 1.0)
    return tuple(zones), min(1.0, quality / 10.0)


def _zone_balance_ticket(
    history: tuple[CausalDrawRow, ...],
) -> tuple[int, ...]:
    if len(history) > 1 and history[0].draw > history[-1].draw:
        history = tuple(reversed(history))
    zones, _quality = _dynamic_zone_partition(history)
    zone_counts = [0] * len(zones)
    for draw in history[-min(len(history), 80) :]:
        for number in draw.numbers:
            for index, zone in enumerate(zones):
                if min(zone) <= number <= max(zone):
                    zone_counts[index] += 1
                    break

    recent_zone_counts = [0] * len(zones)
    for draw in history[-20:]:
        for number in draw.numbers:
            for index, zone in enumerate(zones):
                if min(zone) <= number <= max(zone):
                    recent_zone_counts[index] += 1
                    break

    total = sum(zone_counts) if sum(zone_counts) > 0 else 1
    recent_total = (
        sum(recent_zone_counts) if sum(recent_zone_counts) > 0 else 1
    )
    targets = [
        round(
            (
                zone_counts[index] / total * 0.7
                + recent_zone_counts[index] / recent_total * 0.3
            )
            * _PICK
        )
        for index in range(len(zones))
    ]
    while sum(targets) < _PICK:
        targets[targets.index(min(targets))] += 1
    while sum(targets) > _PICK:
        targets[targets.index(max(targets))] -= 1

    frequency: Counter[int] = Counter(
        number for draw in history for number in draw.numbers
    )
    predicted: list[int] = []
    for index, zone in enumerate(zones):
        zone_scores: list[tuple[int, float]] = []
        for number in zone:
            recent_frequency = sum(
                1
                for draw in history[-30:]
                for candidate in draw.numbers
                if candidate == number
            )
            zone_scores.append(
                (
                    number,
                    frequency.get(number, 0) * 0.6
                    + recent_frequency * 0.4,
                )
            )
        zone_scores.sort(key=lambda item: item[1], reverse=True)
        predicted.extend(
            number for number, _score in zone_scores[: targets[index]]
        )
    return _ticket(predicted)


class BigLottoZoneBalanceFiveAdapter(PortfolioBetAdapter):
    """Main 500-window ticket, then 100/200/300/500 comparisons."""

    strategy_id = (
        "legacy_biglotto__predict_biglotto_115000002_zone_balance__8febca575f5d"
    )
    strategy_name = "大樂透 Zone Balance 500 五位置組合"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 5

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        main_500 = _zone_balance_ticket(history[-500:])
        comparisons = tuple(
            _zone_balance_ticket(history[-window:])
            for window in _ZONE_BALANCE_WINDOWS
        )
        return (main_500, *comparisons)


def _gemini_markov_ticket(
    history: tuple[CausalDrawRow, ...],
) -> tuple[int, ...]:
    transitions: defaultdict[int, Counter[int]] = defaultdict(Counter)
    for index in range(len(history) - 1):
        for number in set(history[index].numbers):
            for next_number in set(history[index + 1].numbers):
                transitions[number][next_number] += 1
    scores: Counter[int] = Counter()
    for number in set(history[-1].numbers):
        for next_number, count in transitions[number].items():
            scores[next_number] += count
    selected = [number for number, _count in scores.most_common(_PICK)]
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        if number not in selected:
            selected.append(number)
        if len(selected) >= _PICK:
            break
    return _ticket(selected[:_PICK])


def _gemini_statistical_ticket(
    history: tuple[CausalDrawRow, ...],
) -> tuple[int, ...]:
    frequency: Counter[int] = Counter(
        number for draw in history[-100:] for number in draw.numbers
    )
    gaps: dict[int, int] = {}
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        gaps[number] = 0
        for index, draw in enumerate(reversed(history)):
            if number in draw.numbers:
                gaps[number] = index
                break
    scores = {
        number: frequency.get(number, 0) * 0.6 + gaps.get(number, 0) * 0.4
        for number in range(_MIN_NUM, _MAX_NUM + 1)
    }
    ranked = sorted(scores, key=lambda number: scores[number], reverse=True)
    return _ticket(ranked[:_PICK])


def _gemini_deviation_ticket(
    history: tuple[CausalDrawRow, ...],
) -> tuple[int, ...]:
    expected = sum(len(draw.numbers) for draw in history) / _MAX_NUM
    frequency: Counter[int] = Counter(
        number for draw in history for number in draw.numbers
    )
    scores = {
        number: expected - frequency.get(number, 0)
        for number in range(_MIN_NUM, _MAX_NUM + 1)
    }
    ranked = sorted(scores, key=lambda number: scores[number], reverse=True)
    return _ticket(ranked[:_PICK])


def _gemini_frequency_ticket(
    history: tuple[CausalDrawRow, ...],
) -> tuple[int, ...]:
    frequency: Counter[int] = Counter(
        number for draw in history[-50:] for number in draw.numbers
    )
    return _ticket(
        [number for number, _count in frequency.most_common(_PICK)]
    )


def _gemini_trend_ticket(
    history: tuple[CausalDrawRow, ...],
) -> tuple[int, ...]:
    recent: Counter[int] = Counter(
        number for draw in history[-20:] for number in draw.numbers
    )
    medium: Counter[int] = Counter(
        number for draw in history[-50:-20] for number in draw.numbers
    )
    scores: dict[int, float] = {}
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        recent_rate = recent.get(number, 0) / 20
        medium_rate = (
            medium.get(number, 0) / 30
            if medium.get(number, 0)
            else 0.01
        )
        scores[number] = recent_rate / max(medium_rate, 0.01)
    ranked = sorted(scores, key=lambda number: scores[number], reverse=True)
    return _ticket(ranked[:_PICK])


def _gemini_bayesian_ticket(
    history: tuple[CausalDrawRow, ...],
) -> tuple[int, ...]:
    prior = 1.0 / _MAX_NUM
    frequency: Counter[int] = Counter(
        number for draw in history for number in draw.numbers
    )
    total = sum(frequency.values())
    posterior = {
        number: (
            frequency.get(number, 0) / total if total > 0 else prior
        )
        * prior
        for number in range(_MIN_NUM, _MAX_NUM + 1)
    }
    total_posterior = sum(posterior.values())
    if total_posterior > 0:
        posterior = {
            number: value / total_posterior
            for number, value in posterior.items()
        }
    ranked = sorted(posterior, key=lambda number: -posterior[number])
    return _ticket(ranked[:_PICK])


def _gemini_hot_cold_ticket(
    history: tuple[CausalDrawRow, ...],
) -> tuple[int, ...]:
    recent: Counter[int] = Counter(
        number for draw in history[-30:] for number in draw.numbers
    )
    hot = [number for number, _count in recent.most_common(4)]
    cold = [
        number
        for number in range(_MIN_NUM, _MAX_NUM + 1)
        if recent.get(number, 0) == 0
    ]
    if len(cold) < 3:
        cold = [number for number, _count in recent.most_common()[-3:]]
    selected = hot[:3] + cold[:3]
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        if number not in selected and len(selected) < _PICK:
            selected.append(number)
    return _ticket(selected[:_PICK])


class BigLottoGeminiPhaseTwoVerifierAdapter(PortfolioBetAdapter):
    """Seven frozen Gemini Phase 2 method tickets in claim order."""

    strategy_id = (
        "legacy_biglotto__verify_gemini_phase2_claim__6407a8f39519"
    )
    strategy_name = "大樂透 Gemini Phase 2 七方法驗證組合"
    strategy_version = "v0.1"
    min_history = 100
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 7

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return (
            _gemini_markov_ticket(history),
            _gemini_statistical_ticket(history),
            _gemini_deviation_ticket(history),
            _gemini_frequency_ticket(history),
            _gemini_trend_ticket(history),
            _gemini_bayesian_ticket(history),
            _gemini_hot_cold_ticket(history),
        )


__all__ = [
    "BigLottoAttentionReplayAdapter",
    "BigLottoFiveMeAdapter",
    "BigLottoGeminiPhaseTwoVerifierAdapter",
    "BigLottoSmartTwoBetAdapter",
    "BigLottoZoneBalanceFiveAdapter",
]
