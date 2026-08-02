"""BigLotto native-strategy Wave 7 frozen BACKTESTED portfolio ports.

The three adapters preserve fixed, positional portfolios from donor commit
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
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter
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
    "BigLottoFiveMeAdapter",
    "BigLottoGeminiPhaseTwoVerifierAdapter",
    "BigLottoSmartTwoBetAdapter",
]
