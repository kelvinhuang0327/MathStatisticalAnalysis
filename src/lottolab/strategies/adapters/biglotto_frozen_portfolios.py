"""Historical BIG_LOTTO portfolio compositions from the frozen research catalog."""

from __future__ import annotations

from collections import Counter
from itertools import pairwise

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters import biglotto_composite_quick_predict_5bet as composite
from lottolab.strategies.adapters import biglotto_quad_strike as quad
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter

type History = tuple[CausalDrawRow, ...]
type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]

_NUMBERS = range(1, 50)


def _used(tickets: Portfolio) -> set[int]:
    return {number for ticket in tickets for number in ticket}


def _triple(history: History, *, sum_constraint: bool = False) -> Portfolio:
    fourier = quad._fourier_rhythm_ticket(history)
    cold = (
        composite._cold_numbers_bet(history, set(fourier))
        if sum_constraint
        else quad._cold_numbers_ticket(history, frozenset(fourier))
    )
    tail = quad._tail_balance_ticket(history, frozenset(fourier + cold))
    return fourier, cold, tail


def _five(history: History, *, frequency_window: int, sum_constraint: bool = False) -> Portfolio:
    triple = _triple(history, sum_constraint=sum_constraint)
    markov = composite._markov_orthogonal_bet(history, _used(triple), 30)
    four = (*triple, markov)
    return (*four, composite._frequency_orthogonal_bet(history, _used(four), frequency_window))


class _FrozenPortfolio(PortfolioBetAdapter):
    supported_lottery_types = (LotteryType.BIG_LOTTO,)


class FcfVersusTripleStrike(_FrozenPortfolio):
    strategy_id = "legacy_biglotto__backtest_fcf_vs_ts3__efc61a551730"
    strategy_version = "legacy-source-49a25effa62f-efc61a551730"
    strategy_name = "TS3 and FCF paired portfolios"
    native_ticket_count = 6
    min_history = 150

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        triple = _triple(history)
        first_two = triple[:2]
        frequent = composite._frequency_orthogonal_bet(history, _used(first_two), 100)
        return *triple, *first_two, frequent


class PortfolioOptimizer(_FrozenPortfolio):
    strategy_id = "legacy_biglotto__portfolio_optimizer__1a6efc7959b6"
    strategy_version = "legacy-source-49a25effa62f-1a6efc7959b6"
    strategy_name = "P3 verified portfolio optimizer"
    native_ticket_count = 5
    min_history = 200

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        return _five(history, frequency_window=200)


class OptimalMatrix(_FrozenPortfolio):
    strategy_id = "legacy_biglotto__optimal_2bet_3bet_matrix__6e5aec296145"
    strategy_version = "legacy-source-49a25effa62f-6e5aec296145"
    strategy_name = "Full five-ticket matrix before subset selection"
    native_ticket_count = 5
    min_history = 200

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        return _five(history, frequency_window=100)


class QuickPredict(_FrozenPortfolio):
    strategy_id = "legacy_biglotto__quick_predict__86259fc99c70"
    strategy_version = "legacy-source-49a25effa62f-86259fc99c70"
    strategy_name = "Quick Predict default Big Lotto portfolio"
    native_ticket_count = 5
    min_history = 50

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        return _five(history, frequency_window=100, sum_constraint=True)


class EwmaSixBet(_FrozenPortfolio):
    strategy_id = "legacy_biglotto__backtest_biglotto_6bet_ewma__e1b5e100d254"
    strategy_version = "legacy-source-49a25effa62f-e1b5e100d254"
    strategy_name = "Five-ticket baseline and both six-ticket EWMA variants"
    native_ticket_count = 17
    min_history = 200

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        baseline = _five(history, frequency_window=100)
        used = _used(baseline)
        remaining = [n for n in _NUMBERS if n not in used]
        total = Counter(n for row in history for n in row.numbers)
        drift = {}
        for n in remaining:
            long_frequency = total[n] / len(history)
            ewma = long_frequency
            for row in history:
                ewma = 0.2 * (n in row.numbers) + 0.8 * ewma
            drift[n] = ewma - long_frequency
        high = tuple(sorted(sorted(remaining, key=drift.__getitem__, reverse=True)[:6]))
        low = tuple(sorted(sorted(remaining, key=drift.__getitem__)[:6]))
        return *baseline, *baseline, high, *baseline, low


class MarkovRepeat(_FrozenPortfolio):
    strategy_id = "legacy_biglotto__backtest_markov_repeat_exception__9bd283fca5f3"
    strategy_version = "legacy-source-49a25effa62f-9bd283fca5f3"
    strategy_name = "Markov repeat-exception sensitivity portfolios"
    native_ticket_count = 24
    min_history = 150

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        triple = _triple(history)
        used = _used(triple)
        last = set(history[-1].numbers)
        repeated = last.intersection(history[-2].numbers)
        scores = _transition_counts(history, 30)
        maximum = max(scores.values())
        remaining = [n for n in _NUMBERS if n not in used]
        tickets: list[Ticket] = []
        for boost in (0.0, 0.1, 0.2, 0.3, 0.5, 1.0):
            boosted = {n: scores[n] + maximum * boost * (n in repeated) for n in remaining}
            markov = tuple(sorted(sorted(remaining, key=boosted.__getitem__, reverse=True)[:6]))
            tickets.extend((*triple, markov))
        return tuple(tickets)


class MarkovFourBet(_FrozenPortfolio):
    strategy_id = "legacy_biglotto__backtest_biglotto_markov_4bet__aefb54eb345b"
    strategy_version = "legacy-source-49a25effa62f-aefb54eb345b"
    strategy_name = "Triple Strike and six Markov window portfolios"
    native_ticket_count = 27
    min_history = 150

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        triple = _triple(history, sum_constraint=True)
        used = _used(triple)
        tickets = list(triple)
        for window in (100, 30, 50, 100, 200, 500):
            tickets.extend((*triple, composite._markov_orthogonal_bet(history, used, window)))
        return tuple(tickets)


class PredictionAnalysis(_FrozenPortfolio):
    strategy_id = "legacy_biglotto__analyze_prediction_115000019__021e1c5ede7b"
    strategy_version = "legacy-source-49a25effa62f-021e1c5ede7b"
    strategy_name = "Historical P0, Triple Strike, Markov and frequency portfolios"
    native_ticket_count = 14
    min_history = 500

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        recent = history[-50:]
        counts = Counter(n for row in recent for n in row.numbers)
        echo = history[-2].numbers
        expected = len(recent) * 6 / 49
        scores = {n: counts[n] - expected + 1.5 * (n in echo) for n in _NUMBERS}
        hot = sorted((n for n in _NUMBERS if scores[n] > 1), key=scores.__getitem__, reverse=True)[
            :6
        ]
        middle = sorted(_NUMBERS, key=lambda n: abs(scores[n]))
        hot.extend([n for n in middle if n not in hot][: 6 - len(hot)])
        cold = sorted(
            (n for n in _NUMBERS if scores[n] < -1 and n not in hot), key=scores.__getitem__
        )[:6]
        cold.extend([n for n in _NUMBERS if n not in hot and n not in cold][: 6 - len(cold)])
        five = _five(history, frequency_window=200)
        return tuple(sorted(hot)), tuple(sorted(cold)), *five[:3], *five[:4], *five


def _unfiltered_fourier_rank(history: History, *, include_zero: bool) -> tuple[int, ...]:
    """These donors retain all positive FFT periods, including the longest period."""
    rows = history[-500:]
    width = len(rows)
    scores = [0.0] * 50
    for number in _NUMBERS:
        bits = tuple(int(number in row.numbers) for row in rows)
        count = sum(bits)
        if count < 2:
            continue
        mean = count / width
        spectrum = quad._pocketfft_real_packed(tuple(bit - mean for bit in bits))
        peak = max(
            range(1, (width - 1) // 2 + 1),
            key=lambda i: quad._legacy_complex_magnitude(spectrum[2 * i - 1], spectrum[2 * i]),
        )
        period = 1.0 / (peak * (1.0 / width))
        gap = bits[::-1].index(1)
        scores[number] = 1.0 / (abs(gap - period) + 1.0)
    offset = 0 if include_zero else 1
    return tuple(i + offset for i in reversed(quad._legacy_numpy_argsort(tuple(scores[offset:]))))


def _echo_ticket(history: History, first_two: Portfolio) -> Ticket:
    used = _used(first_two)
    echo = [n for n in history[-2].numbers if n not in used]
    frequency = Counter(n for row in history[-100:] for n in row.numbers)
    remainder = sorted(
        (n for n in _NUMBERS if n not in used and n not in echo), key=frequency.__getitem__
    )
    return tuple(sorted((echo + remainder)[:6]))


class PowerPrecisionThree(_FrozenPortfolio):
    strategy_id = "legacy_biglotto__backtest_big_lotto_3bet__245f477b3e77"
    strategy_version = "legacy-source-49a25effa62f-245f477b3e77"
    strategy_name = "Big Lotto Power Precision three-ticket portfolio"
    native_ticket_count = 3
    min_history = 500

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        rank = _unfiltered_fourier_rank(history, include_zero=True)
        start = int(rank[0] == 0)
        second = start + 6
        second += int(rank[second] == 0)
        bets = (tuple(sorted(rank[start : start + 6])), tuple(sorted(rank[second : second + 6])))
        return *bets, _echo_ticket(history, bets)


class LagTwoSixBet(_FrozenPortfolio):
    strategy_id = "legacy_biglotto__backtest_biglotto_6bet__f5d8c03421d2"
    strategy_version = "legacy-source-49a25effa62f-f5d8c03421d2"
    strategy_name = "Five baseline tickets and six-ticket lag-two portfolio"
    native_ticket_count = 11
    min_history = 200

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        rank = _unfiltered_fourier_rank(history, include_zero=False)
        first_two = (tuple(sorted(rank[:6])), tuple(sorted(rank[6:12])))
        three = *first_two, _echo_ticket(history, first_two)
        used = _used(three)
        frequency = Counter(n for row in history[-100:] for n in row.numbers)
        leftover = sorted(
            (n for n in _NUMBERS if n not in used), key=frequency.__getitem__, reverse=True
        )
        five = *three, tuple(sorted(leftover[:6])), tuple(sorted(leftover[6:12]))
        used = _used(five)
        recent = Counter(n for row in history[-50:] for n in row.numbers)
        echo = history[-2].numbers
        final = sorted(
            (n for n in _NUMBERS if n not in used),
            key=lambda n: recent[n] * (1.5 if n in echo else 1),
            reverse=True,
        )
        return *five, *five, tuple(sorted(final[:6]))


class TripleStrikeV2(_FrozenPortfolio):
    strategy_id = "legacy_biglotto__backtest_biglotto_triple_strike_v2__977a7cf65c8f"
    strategy_version = "legacy-source-49a25effa62f-977a7cf65c8f"
    strategy_name = "Cycle, structural defense and extreme compensation"
    native_ticket_count = 3
    min_history = 500

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        first = tuple(sorted(_unfiltered_fourier_rank(history, include_zero=True)[:6]))
        numbers = [n for row in history[-100:] for n in row.numbers]
        freq = Counter(numbers)
        tail = Counter(n % 10 for n in numbers).most_common(1)[0][0]
        seed = max((n for n in range(1, 49) if n not in first), key=freq.__getitem__)
        # The frozen source excludes earlier numbers when choosing the seed, not its successor.
        candidates = [seed, seed + 1]
        candidates.extend(
            [n for n in range(1, 49) if n % 10 == tail and n not in first and n not in candidates][
                :2
            ]
        )
        others = sorted(
            (n for n in _NUMBERS if n not in first and n not in candidates),
            key=freq.__getitem__,
            reverse=True,
        )
        second = tuple(sorted((candidates + others)[:6]))
        available = [n for n in _NUMBERS if n not in first and n not in second]
        available.sort(key=lambda n: quad._full_history_gap(history, n), reverse=True)
        return first, second, tuple(sorted(available[:6]))


class DirectionThree(_FrozenPortfolio):
    strategy_id = "legacy_biglotto__backtest_direction_3__91f93b31efb5"
    strategy_version = "legacy-source-49a25effa62f-91f93b31efb5"
    strategy_name = "Triple Strike and stabilized gray-gap portfolios"
    native_ticket_count = 6
    min_history = 500

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        triple = _triple(history)
        used = _used(triple[:2])
        freq = Counter(n for row in history[-50:] for n in row.numbers)
        gray = [n for n in _NUMBERS if n not in used and -1.5 <= freq[n] - 300 / 49 <= 1.5]
        gray.sort(key=lambda n: quad._full_history_gap(history, n), reverse=True)
        # When fewer than six qualify, preserve the source's short ticket for validation.
        return *triple, *triple[:2], tuple(sorted(gray[:6]))


def _transition_counts(history: History, window: int) -> Counter[int]:
    last = set(history[-1].numbers)
    scores: Counter[int] = Counter()
    for previous, following in pairwise(history[-window:]):
        weight = len(last.intersection(previous.numbers))
        for n in following.numbers:
            scores[n] += weight
    return scores


class MarkovVersusTriple(_FrozenPortfolio):
    strategy_id = "legacy_biglotto__verify_markov_vs_triple_2bet__2094ee4bc361"
    strategy_version = "legacy-source-49a25effa62f-2094ee4bc361"
    strategy_name = "Paired Markov and Triple Strike two-ticket portfolios"
    native_ticket_count = 4
    min_history = 501

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        counts = _transition_counts(history, 100)
        ranked = sorted(_NUMBERS, key=counts.__getitem__, reverse=True)
        first = quad._fourier_rhythm_ticket(history)
        return (
            tuple(ranked[:6]),
            tuple(ranked[6:12]),
            first,
            quad._cold_numbers_ticket(history, frozenset(first)),
        )


class RegimeFormulaGrid(_FrozenPortfolio):
    strategy_id = "legacy_biglotto__rgf_walkforward_validator__cab0d1127b62"
    strategy_version = "legacy-source-49a25effa62f-cab0d1127b62"
    strategy_name = "Six pre-target RGF candidate formulas"
    native_ticket_count = 6
    min_history = 200

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        counts = Counter(n for row in history[-100:] for n in row.numbers)
        last_seen = {n: i for i, row in enumerate(history) for n in row.numbers}
        gaps = [len(history) - last_seen.get(n, 0) for n in _NUMBERS]
        max_gap = max(gaps)
        transitions = _transition_counts(history, 30)
        total = sum(transitions.values())
        vectors = []
        for n, raw_gap in zip(_NUMBERS, gaps, strict=True):
            freq = counts[n] / 100
            gap = raw_gap / (max_gap + 1e-9)
            markov = transitions[n] / (total + 1e-9)
            vectors.append(
                (freq * gap, freq * markov, gap * markov, freq + gap, freq + markov, freq)
            )
        return tuple(
            tuple(sorted(i + 1 for i in quad._legacy_numpy_argsort(scores)[-6:]))
            for scores in zip(*vectors, strict=True)
        )


def _structural_counts(history: History, window: int) -> tuple[int, Counter[int]]:
    rows = history[-window:]
    sums = [sum(row.numbers) for row in rows]
    mean = sum(sums) / len(sums)
    deviation = (sum((value - mean) ** 2 for value in sums) / len(sums)) ** 0.5

    def group(row: CausalDrawRow) -> tuple[int, int]:
        draw_sum = sum(row.numbers)
        tier = -1 if draw_sum < mean - 0.5 * deviation else int(draw_sum > mean + 0.5 * deviation)
        if sum(n <= 16 for n in row.numbers) >= 3:
            return tier, 1
        return tier, 3 if sum(n >= 33 for n in row.numbers) >= 3 else 2

    target_group = group(rows[-1])
    following = [b for a, b in pairwise(rows) if group(a) == target_group]
    return len(following), Counter(n for row in following for n in row.numbers)


class StructuralGroup(_FrozenPortfolio):
    strategy_id = "legacy_biglotto__backtest_structural_group__2fc42ff67ab1"
    strategy_version = "legacy-source-49a25effa62f-2fc42ff67ab1"
    strategy_name = "Triple Strike, structural reversion and structural cold portfolios"
    native_ticket_count = 10
    min_history = 150

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        triple = _triple(history)
        used = _used(triple)
        samples, counts = _structural_counts(history, 300)
        if samples < 5:
            counts = Counter(n for row in history[-300:] for n in row.numbers)
        extra = sorted(
            (n for n in _NUMBERS if n not in used), key=counts.__getitem__, reverse=True
        )[:6]
        first, cold, _ = triple
        samples, counts = _structural_counts(history, 200)
        if samples >= 5:
            cold = tuple(
                sorted(sorted((n for n in _NUMBERS if n not in first), key=counts.__getitem__)[:6])
            )
        tail = quad._tail_balance_ticket(history, frozenset(first + cold))
        return *triple, *triple, tuple(sorted(extra)), first, cold, tail
