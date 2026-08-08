"""Pure POWER_LOTTO adapters for the first cross-lottery migration wave.

Wave 1 and Wave 2 (:mod:`.powerlotto_wave1`, :mod:`.powerlotto_wave2`) port
POWER_LOTTO-native donor code. This wave instead ports nine BIG_LOTTO
main-number algorithm families from the live 59-strategy BIG_LOTTO catalog
(``lottolab.strategies.catalog``) whose portability ledger classification is
``PORTABLE_DIRECT`` or ``PORTABLE_WITH_GAMESPEC``.  Owner-authorized Waves 4
and 5 extend this preserved module to the exhaustive portable set; the task
ledger is the authority for the final 59-row classification.

Each predictor below is a faithful re-expression of one BIG_LOTTO adapter's
``_predict``/``_predict_all`` body, with the pool/pick game constants
(``_POOL``/``_PICK``) switched from BIG_LOTTO's 1..49/6 to POWER_LOTTO's
1..38/6 via this project's ``POWER_LOTTO_RULE_CONTRACT``. No BIG_LOTTO source
file is imported or modified; this module is fully self-contained and BIG_LOTTO
behavior is unchanged by its existence. Native ticket count and ticket order
are preserved exactly from the BIG_LOTTO donor. The second-zone number is
never computed here -- :class:`~.powerlotto_wave1.P638StrategySpec` pairs
every returned first-zone ticket with the shared
:func:`lottolab.strategies.powerlotto_second_zone.second_zone_predict` SSOT.
Like every strategy in Wave 1 and Wave 2, every predictor here is a
deterministic pure function of causal history alone.  The final eight
non-portable donor families are recorded below; former batch-size deferrals
are intentionally absent because Waves 4 and 5 now implement them.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from itertools import combinations
from typing import Final

from lottolab.domain.lottery_rules import POWER_LOTTO_RULE_CONTRACT
from lottolab.strategies.adapters.powerlotto_wave1 import (
    P638BlockedStrategy,
    P638FirstZoneTicketSet,
    P638HistoryRow,
    P638StrategySpec,
)

_POOL: Final = POWER_LOTTO_RULE_CONTRACT.main_number_max
_MIN_NUM: Final = POWER_LOTTO_RULE_CONTRACT.main_number_min
_PICK: Final = POWER_LOTTO_RULE_CONTRACT.main_number_count

_DONOR_SHA256 = "a867d33c130daa8de00363df5ee52ca926385a8ef2c17f03b161a8b6726adf43"


def _ticket(numbers: list[int]) -> tuple[int, ...]:
    """Sort, validate, and freeze one candidate list into a legal first-zone ticket."""

    values = tuple(sorted(numbers))
    if (
        len(values) != _PICK
        or len(set(values)) != _PICK
        or any(type(number) is not int or not _MIN_NUM <= number <= _POOL for number in values)
    ):
        raise ValueError("WAVE3_INVALID_TICKET")
    return values


# ─── power_biglotto_deviation_2bet — port of biglotto_selected.py's
#     _deviation_complement_2bet (BIG_LOTTO strategy_id biglotto_deviation_2bet
#     / biglotto_deviation_2bet_bet2, collapsed into one native 2-ticket
#     portfolio: hot bet then cold complement bet).

_DEVIATION_WINDOW: Final = 50
_DEVIATION_HOT_THRESHOLD: Final = 1
_DEVIATION_COLD_THRESHOLD: Final = -1


def _deviation_tickets(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    recent = history[-_DEVIATION_WINDOW:] if len(history) > _DEVIATION_WINDOW else history
    total = len(recent)
    expected = total * _PICK / _POOL

    freq: dict[int, int] = {}
    for row in recent:
        for number in row.numbers:
            freq[number] = freq.get(number, 0) + 1

    hot: list[tuple[int, float]] = []
    cold: list[tuple[int, float]] = []
    for number in range(_MIN_NUM, _POOL + 1):
        deviation = freq.get(number, 0) - expected
        if deviation > _DEVIATION_HOT_THRESHOLD:
            hot.append((number, deviation))
        elif deviation < _DEVIATION_COLD_THRESHOLD:
            cold.append((number, abs(deviation)))

    hot.sort(key=lambda candidate: candidate[1], reverse=True)
    cold.sort(key=lambda candidate: candidate[1], reverse=True)

    bet1 = [number for number, _ in hot[:_PICK]]
    used = set(bet1)
    if len(bet1) < _PICK:
        nearest_expected = sorted(
            range(_MIN_NUM, _POOL + 1), key=lambda number: abs(freq.get(number, 0) - expected)
        )
        for number in nearest_expected:
            if number not in used and len(bet1) < _PICK:
                bet1.append(number)
                used.add(number)

    bet2: list[int] = []
    for number, _ in cold:
        if number not in used and len(bet2) < _PICK:
            bet2.append(number)
            used.add(number)
    if len(bet2) < _PICK:
        for number in range(_MIN_NUM, _POOL + 1):
            if number not in used and len(bet2) < _PICK:
                bet2.append(number)
                used.add(number)

    return (_ticket(bet1), _ticket(bet2))


# ─── power_biglotto_p0_echo_2bet — port of biglotto_selected.py's
#     _p0_hot_echo_2bets (BIG_LOTTO strategy_id biglotto_p0_2bet_bet1/bet2,
#     collapsed into one native 2-ticket portfolio: hot+echo bet then cold
#     complement bet).

_P0_WINDOW: Final = 50
_P0_ECHO_BOOST: Final = 1.5
_P0_HOT_THRESHOLD: Final = 1
_P0_COLD_THRESHOLD: Final = -1


def _p0_echo_tickets(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    recent = history[-_P0_WINDOW:] if len(history) > _P0_WINDOW else history
    expected = len(recent) * _PICK / _POOL

    frequencies: dict[int, int] = {}
    for row in recent:
        for number in row.numbers:
            frequencies[number] = frequencies.get(number, 0) + 1

    scores = {
        number: frequencies.get(number, 0) - expected for number in range(_MIN_NUM, _POOL + 1)
    }
    if len(history) >= 3:
        for number in history[-2].numbers:
            if number <= _POOL:
                scores[number] += _P0_ECHO_BOOST

    hot = sorted(
        ((number, score) for number, score in scores.items() if score > _P0_HOT_THRESHOLD),
        key=lambda candidate: (-candidate[1], candidate[0]),
    )
    cold = sorted(
        ((number, score) for number, score in scores.items() if score < _P0_COLD_THRESHOLD),
        key=lambda candidate: (candidate[1], candidate[0]),
    )
    bet1 = [number for number, _ in hot[:_PICK]]
    used = set(bet1)
    if len(bet1) < _PICK:
        nearest_expected = sorted(
            range(_MIN_NUM, _POOL + 1), key=lambda number: (abs(scores[number]), number)
        )
        for number in nearest_expected:
            if number not in used and len(bet1) < _PICK:
                bet1.append(number)
                used.add(number)

    bet2: list[int] = []
    for number, _ in cold:
        if number not in used and len(bet2) < _PICK:
            bet2.append(number)
            used.add(number)
    if len(bet2) < _PICK:
        for number in range(_MIN_NUM, _POOL + 1):
            if number not in used and len(bet2) < _PICK:
                bet2.append(number)
                used.add(number)

    return (_ticket(bet1), _ticket(bet2))


# ─── power_biglotto_graph_predictor_1bet — port of biglotto_wave1.py's
#     BigLottoGraphPredictorAdapter (strategy_id
#     legacy_biglotto__graph_predictor__cd70713a5709): PageRank-centrality +
#     greedy-clique co-occurrence graph.


def _graph_build_graph(history: tuple[P638HistoryRow, ...]) -> dict[int, dict[int, float]]:
    adj: dict[int, dict[int, float]] = {}
    for i, draw in enumerate(reversed(history)):
        weight = math.exp(-0.02 * i)
        nums = draw.numbers
        for a, b in combinations(nums, 2):
            adj.setdefault(a, {})
            adj.setdefault(b, {})
            adj[a][b] = adj[a].get(b, 0.0) + weight
            adj[b][a] = adj[b].get(a, 0.0) + weight
    return adj


def _graph_pagerank(
    adj: dict[int, dict[int, float]], damping: float = 0.85, iterations: int = 20
) -> dict[int, float]:
    nodes = list(range(_MIN_NUM, _POOL + 1))
    rank = dict.fromkeys(nodes, 1.0 / _POOL)
    for _ in range(iterations):
        new_rank: dict[int, float] = {}
        for n in nodes:
            incoming = sum(
                adj[m].get(n, 0.0) * rank[m] / max(sum(adj[m].values()), 1)
                for m in nodes
                if m in adj and adj[m].get(n, 0.0) > 0
            )
            new_rank[n] = (1 - damping) / _POOL + damping * incoming
        rank = new_rank
    return rank


def _graph_select_clique(
    adj: dict[int, dict[int, float]], candidates: list[int]
) -> tuple[int, ...]:
    selected: list[int] = []
    remaining = list(candidates)
    while len(selected) < _PICK and remaining:
        best: int | None = None
        best_score = -1.0
        for c in remaining:
            score = sum(adj.get(c, {}).get(s, 0.0) for s in selected) + 0.1
            if score > best_score:
                best_score = score
                best = c
        if best is not None:
            selected.append(best)
            remaining.remove(best)
    return _ticket(selected)


def _graph_predictor_tickets(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    adj = _graph_build_graph(history)
    rank = _graph_pagerank(adj)
    sorted_by_rank = sorted(rank.items(), key=lambda item: item[1], reverse=True)
    top_candidates = [n for n, _ in sorted_by_rank[:15]]
    return (_graph_select_clique(adj, top_candidates),)


# ─── power_biglotto_must_hit_top6_1bet — port of biglotto_wave1.py's
#     BigLottoMustHitTop6Adapter (strategy_id
#     legacy_biglotto__backtest_must_hit__909c91fd2fd0): top-6-most-frequent
#     in the last 50 draws. Pool-agnostic as written; ported unchanged.


def _must_hit_top6_tickets(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    freq = Counter(n for draw in history[-50:] for n in draw.numbers)
    return (_ticket([n for n, _ in freq.most_common(_PICK)]),)


# ─── power_biglotto_dynamic_frequency_1bet — port of biglotto_wave1.py's
#     BigLottoDynamicFrequencyAdapter (strategy_id
#     legacy_biglotto__dynamic_frequency_predictor__36e5bf9998ac): self-tuning
#     frequency window, best of 5 frozen windows via an internal backtest.
#     Pool-agnostic as written; ported unchanged.

_DYNAMIC_FREQUENCY_WINDOWS: Final = (30, 50, 100, 200, 300)
_DYNAMIC_FREQUENCY_LOOKBACK: Final = 50


def _dynamic_frequency_predict(history: tuple[P638HistoryRow, ...], window: int) -> tuple[int, ...]:
    recent = history[-window:] if len(history) > window else history
    all_nums = [n for draw in recent for n in draw.numbers]
    freq = Counter(all_nums)
    return _ticket([n for n, _ in freq.most_common(_PICK)])


def _dynamic_frequency_optimal_window(history: tuple[P638HistoryRow, ...]) -> int:
    lookback = _DYNAMIC_FREQUENCY_LOOKBACK
    window_scores: dict[int, float] = {}
    for window in _DYNAMIC_FREQUENCY_WINDOWS:
        total_hits = 0
        for i in range(lookback):
            test_idx = len(history) - lookback + i
            prefix = history[:test_idx]
            actual = set(history[test_idx].numbers)
            predicted = set(_dynamic_frequency_predict(prefix, window))
            total_hits += len(predicted & actual)
        window_scores[window] = total_hits / lookback
    return max(window_scores, key=lambda window: window_scores[window])


def _dynamic_frequency_tickets(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    best_window = _dynamic_frequency_optimal_window(history)
    return (_dynamic_frequency_predict(history, best_window),)


# ─── power_biglotto_hot_cooccurrence_1bet — port of biglotto_wave1.py's
#     BigLottoHotCooccurrenceAdapter (strategy_id
#     legacy_biglotto__hot_cooccurrence_analyzer__48121f27d7ee): hot-number +
#     co-occurrence-weighted predictor.


def _cooccurrence_hot_numbers(
    history: tuple[P638HistoryRow, ...], window_size: int
) -> list[tuple[int, int]]:
    recent = history[-window_size:] if len(history) > window_size else history
    all_numbers = [n for draw in recent for n in draw.numbers]
    return Counter(all_numbers).most_common(None)


def _cooccurrence_matrix(
    history: tuple[P638HistoryRow, ...], window_size: int
) -> dict[int, dict[int, float]]:
    recent = history[-window_size:] if len(history) > window_size else history
    co: dict[int, dict[int, float]] = {
        i: dict.fromkeys(range(_MIN_NUM, _POOL + 1), 0.0) for i in range(_MIN_NUM, _POOL + 1)
    }
    for draw in recent:
        numbers = draw.numbers
        for i, num1 in enumerate(numbers):
            for num2 in numbers[i + 1 :]:
                co[num1][num2] += 1
                co[num2][num1] += 1
    if len(recent) > 0:
        max_co = len(recent)
        for i in co:
            for j in co[i]:
                co[i][j] = co[i][j] / max_co
    return co


def _cooccurrence_apply_rules(
    hot_numbers: list[int], co_matrix: dict[int, dict[int, float]], cooccurrence_weight: float = 0.3
) -> tuple[int, ...]:
    if len(hot_numbers) <= _PICK:
        return _ticket(hot_numbers)

    scores: dict[int, float] = {}
    for i, num in enumerate(hot_numbers):
        rank_score = (len(hot_numbers) - i) / len(hot_numbers)
        co_scores = [co_matrix[num].get(other, 0.0) for other in hot_numbers if other != num]
        co_score = (sum(co_scores) / len(co_scores)) if co_scores else 0.0
        scores[num] = (1 - cooccurrence_weight) * rank_score + cooccurrence_weight * co_score

    sorted_nums = sorted(scores.keys(), key=lambda n: scores[n], reverse=True)
    return _ticket(sorted_nums[:_PICK])


def _hot_cooccurrence_tickets(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    hot_freq = _cooccurrence_hot_numbers(history, 50)
    hot_nums = [n for n, _ in hot_freq[:20]]
    co_matrix = _cooccurrence_matrix(history, 100)
    return (_cooccurrence_apply_rules(hot_nums, co_matrix),)


# ─── power_biglotto_attention_replay_1bet — port of biglotto_wave7.py's
#     BigLottoAttentionReplayAdapter (strategy_id
#     legacy_biglotto__attention_replay_predictor__a811e2eb8215): frozen
#     15-draw recency-weighted-decay frequency ticket.

_ATTENTION_WEIGHTS: Final = tuple((1.0 + index * 0.1) / 25.5 for index in range(15))


def _attention_replay_tickets(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    weighted_frequency: defaultdict[int, float] = defaultdict(float)
    for index, draw in enumerate(history[-15:]):
        weight = _ATTENTION_WEIGHTS[index]
        for number in draw.numbers:
            weighted_frequency[number] += weight
    ranked = sorted(weighted_frequency.items(), key=lambda item: item[1], reverse=True)
    return (_ticket([number for number, _weight in ranked[:_PICK]]),)


# ─── power_biglotto_zone_balance_5bet — port of biglotto_wave7.py's
#     BigLottoZoneBalanceFiveAdapter (strategy_id
#     legacy_biglotto__predict_biglotto_115000002_zone_balance__8febca575f5d):
#     a main 500-window zone-balance ticket, then 100/200/300/500-window
#     comparisons. Zones are a frequency-rank partition over the whole pool
#     (not fixed number ranges), so this algorithm is pool-size-agnostic as
#     written; ported unchanged apart from the pool bound.

_ZONE_BALANCE_WINDOWS: Final = (100, 200, 300, 500)


def _variance(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _dynamic_zone_partition(
    history: tuple[P638HistoryRow, ...],
) -> tuple[tuple[tuple[int, ...], ...], float]:
    frequency: Counter[int] = Counter(number for draw in history for number in draw.numbers)
    sorted_pairs = sorted(
        ((number, frequency.get(number, 0)) for number in range(_MIN_NUM, _POOL + 1)),
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
        window = sorted_pairs[start_index : start_index + current_size]
        zone = tuple(sorted(number for number, _count in window))
        if zone:
            zones.append(zone)
        start_index += current_size

    zone_means = [sum(frequency.get(number, 0) for number in zone) / len(zone) for zone in zones]
    between_variance = _variance(zone_means)
    within_variances = [
        _variance([float(frequency.get(number, 0)) for number in zone])
        for zone in zones
        if len(zone) > 1
    ]
    average_within = sum(within_variances) / len(within_variances) if within_variances else 1.0
    quality = between_variance / (average_within + 1.0)
    return tuple(zones), min(1.0, quality / 10.0)


def _zone_balance_ticket(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
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
    recent_total = sum(recent_zone_counts) if sum(recent_zone_counts) > 0 else 1
    targets = [
        round(
            (zone_counts[index] / total * 0.7 + recent_zone_counts[index] / recent_total * 0.3)
            * _PICK
        )
        for index in range(len(zones))
    ]
    while sum(targets) < _PICK:
        targets[targets.index(min(targets))] += 1
    while sum(targets) > _PICK:
        targets[targets.index(max(targets))] -= 1

    frequency: Counter[int] = Counter(number for draw in history for number in draw.numbers)
    predicted: list[int] = []
    for index, zone in enumerate(zones):
        zone_scores: list[tuple[int, float]] = []
        for number in zone:
            recent_frequency = sum(
                1 for draw in history[-30:] for candidate in draw.numbers if candidate == number
            )
            zone_scores.append((number, frequency.get(number, 0) * 0.6 + recent_frequency * 0.4))
        zone_scores.sort(key=lambda item: item[1], reverse=True)
        predicted.extend(number for number, _score in zone_scores[: targets[index]])
    return _ticket(predicted)


def _zone_balance_tickets(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    main_500 = _zone_balance_ticket(history[-500:])
    comparisons = tuple(_zone_balance_ticket(history[-window:]) for window in _ZONE_BALANCE_WINDOWS)
    return (main_500, *comparisons)


# ─── power_biglotto_gemini_phase2_7bet — port of biglotto_wave7.py's
#     BigLottoGeminiPhaseTwoVerifierAdapter (strategy_id
#     legacy_biglotto__verify_gemini_phase2_claim__6407a8f39519): seven
#     frozen, independent method tickets (own re-implementations, not the
#     shared Unified engine), in fixed claim order.


def _gemini_markov_ticket(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
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
    for number in range(_MIN_NUM, _POOL + 1):
        if number not in selected:
            selected.append(number)
        if len(selected) >= _PICK:
            break
    return _ticket(selected[:_PICK])


def _gemini_statistical_ticket(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    frequency: Counter[int] = Counter(number for draw in history[-100:] for number in draw.numbers)
    gaps: dict[int, int] = {}
    for number in range(_MIN_NUM, _POOL + 1):
        gaps[number] = 0
        for index, draw in enumerate(reversed(history)):
            if number in draw.numbers:
                gaps[number] = index
                break
    scores = {
        number: frequency.get(number, 0) * 0.6 + gaps.get(number, 0) * 0.4
        for number in range(_MIN_NUM, _POOL + 1)
    }
    ranked = sorted(scores, key=lambda number: scores[number], reverse=True)
    return _ticket(ranked[:_PICK])


def _gemini_deviation_ticket(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    expected = sum(len(draw.numbers) for draw in history) / _POOL
    frequency: Counter[int] = Counter(number for draw in history for number in draw.numbers)
    scores = {number: expected - frequency.get(number, 0) for number in range(_MIN_NUM, _POOL + 1)}
    ranked = sorted(scores, key=lambda number: scores[number], reverse=True)
    return _ticket(ranked[:_PICK])


def _gemini_frequency_ticket(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    frequency: Counter[int] = Counter(number for draw in history[-50:] for number in draw.numbers)
    return _ticket([number for number, _count in frequency.most_common(_PICK)])


def _gemini_trend_ticket(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    recent: Counter[int] = Counter(number for draw in history[-20:] for number in draw.numbers)
    medium: Counter[int] = Counter(number for draw in history[-50:-20] for number in draw.numbers)
    scores: dict[int, float] = {}
    for number in range(_MIN_NUM, _POOL + 1):
        recent_rate = recent.get(number, 0) / 20
        medium_rate = medium.get(number, 0) / 30 if medium.get(number, 0) else 0.01
        scores[number] = recent_rate / max(medium_rate, 0.01)
    ranked = sorted(scores, key=lambda number: scores[number], reverse=True)
    return _ticket(ranked[:_PICK])


def _gemini_bayesian_ticket(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    prior = 1.0 / _POOL
    frequency: Counter[int] = Counter(number for draw in history for number in draw.numbers)
    total = sum(frequency.values())
    posterior = {
        number: (frequency.get(number, 0) / total if total > 0 else prior) * prior
        for number in range(_MIN_NUM, _POOL + 1)
    }
    total_posterior = sum(posterior.values())
    if total_posterior > 0:
        posterior = {number: value / total_posterior for number, value in posterior.items()}
    ranked = sorted(posterior, key=lambda number: -posterior[number])
    return _ticket(ranked[:_PICK])


def _gemini_hot_cold_ticket(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    recent: Counter[int] = Counter(number for draw in history[-30:] for number in draw.numbers)
    hot = [number for number, _count in recent.most_common(4)]
    cold = [number for number in range(_MIN_NUM, _POOL + 1) if recent.get(number, 0) == 0]
    if len(cold) < 3:
        cold = [number for number, _count in recent.most_common()[-3:]]
    selected = hot[:3] + cold[:3]
    for number in range(_MIN_NUM, _POOL + 1):
        if number not in selected and len(selected) < _PICK:
            selected.append(number)
    return _ticket(selected[:_PICK])


def _gemini_phase2_tickets(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    return (
        _gemini_markov_ticket(history),
        _gemini_statistical_ticket(history),
        _gemini_deviation_ticket(history),
        _gemini_frequency_ticket(history),
        _gemini_trend_ticket(history),
        _gemini_bayesian_ticket(history),
        _gemini_hot_cold_ticket(history),
    )


WAVE3_STRATEGIES: tuple[P638StrategySpec, ...] = (
    P638StrategySpec(
        strategy_id="power_biglotto_deviation_2bet",
        strategy_version="v0.1-p638-wave3",
        native_ticket_count=2,
        min_history=100,
        source_paths=("src/lottolab/strategies/adapters/biglotto_selected.py",),
        provenance=(
            "POWER_LOTTO cross-lottery port of BIG_LOTTO strategy "
            "biglotto_deviation_2bet/biglotto_deviation_2bet_bet2 (donor "
            f"archive {_DONOR_SHA256}); hot bet then cold-complement bet "
            "collapsed into one native 2-ticket portfolio."
        ),
        _predictor=_deviation_tickets,
    ),
    P638StrategySpec(
        strategy_id="power_biglotto_p0_echo_2bet",
        strategy_version="v0.1-p638-wave3",
        native_ticket_count=2,
        min_history=1,
        source_paths=("src/lottolab/strategies/adapters/biglotto_selected.py",),
        provenance=(
            "POWER_LOTTO cross-lottery port of BIG_LOTTO strategy "
            "biglotto_p0_2bet_bet1/bet2 (donor archive "
            f"{_DONOR_SHA256}); hot+echo bet then cold-complement bet "
            "collapsed into one native 2-ticket portfolio."
        ),
        _predictor=_p0_echo_tickets,
    ),
    P638StrategySpec(
        strategy_id="power_biglotto_graph_predictor_1bet",
        strategy_version="v0.1-p638-wave3",
        native_ticket_count=1,
        min_history=1,
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave1.py",),
        provenance=(
            "POWER_LOTTO cross-lottery port of BIG_LOTTO strategy "
            "legacy_biglotto__graph_predictor__cd70713a5709 (donor archive "
            f"{_DONOR_SHA256}); PageRank-centrality + greedy-clique "
            "co-occurrence graph."
        ),
        _predictor=_graph_predictor_tickets,
    ),
    P638StrategySpec(
        strategy_id="power_biglotto_must_hit_top6_1bet",
        strategy_version="v0.1-p638-wave3",
        native_ticket_count=1,
        min_history=50,
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave1.py",),
        provenance=(
            "POWER_LOTTO cross-lottery port of BIG_LOTTO strategy "
            "legacy_biglotto__backtest_must_hit__909c91fd2fd0 (donor archive "
            f"{_DONOR_SHA256}); top-6-most-frequent-in-last-50-draws, "
            "pool-agnostic as written."
        ),
        _predictor=_must_hit_top6_tickets,
    ),
    P638StrategySpec(
        strategy_id="power_biglotto_dynamic_frequency_1bet",
        strategy_version="v0.1-p638-wave3",
        native_ticket_count=1,
        min_history=200,
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave1.py",),
        provenance=(
            "POWER_LOTTO cross-lottery port of BIG_LOTTO strategy "
            "legacy_biglotto__dynamic_frequency_predictor__36e5bf9998ac "
            f"(donor archive {_DONOR_SHA256}); self-tuning frequency window, "
            "best of 5 frozen windows via an internal backtest, pool-agnostic "
            "as written."
        ),
        _predictor=_dynamic_frequency_tickets,
    ),
    P638StrategySpec(
        strategy_id="power_biglotto_hot_cooccurrence_1bet",
        strategy_version="v0.1-p638-wave3",
        native_ticket_count=1,
        min_history=1,
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave1.py",),
        provenance=(
            "POWER_LOTTO cross-lottery port of BIG_LOTTO strategy "
            "legacy_biglotto__hot_cooccurrence_analyzer__48121f27d7ee (donor "
            f"archive {_DONOR_SHA256}); hot-number + co-occurrence-weighted "
            "predictor."
        ),
        _predictor=_hot_cooccurrence_tickets,
    ),
    P638StrategySpec(
        strategy_id="power_biglotto_attention_replay_1bet",
        strategy_version="v0.1-p638-wave3",
        native_ticket_count=1,
        min_history=1,
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave7.py",),
        provenance=(
            "POWER_LOTTO cross-lottery port of BIG_LOTTO strategy "
            "legacy_biglotto__attention_replay_predictor__a811e2eb8215 "
            f"(donor archive {_DONOR_SHA256}); frozen 15-draw "
            "recency-weighted-decay frequency ticket."
        ),
        _predictor=_attention_replay_tickets,
    ),
    P638StrategySpec(
        strategy_id="power_biglotto_zone_balance_5bet",
        strategy_version="v0.1-p638-wave3",
        native_ticket_count=5,
        min_history=1,
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave7.py",),
        provenance=(
            "POWER_LOTTO cross-lottery port of BIG_LOTTO strategy "
            "legacy_biglotto__predict_biglotto_115000002_zone_balance__"
            f"8febca575f5d (donor archive {_DONOR_SHA256}); main 500-window "
            "zone-balance ticket then 100/200/300/500-window comparisons; "
            "zones are a frequency-rank partition of the whole pool, "
            "pool-size-agnostic as written."
        ),
        _predictor=_zone_balance_tickets,
    ),
    P638StrategySpec(
        strategy_id="power_biglotto_gemini_phase2_7bet",
        strategy_version="v0.1-p638-wave3",
        native_ticket_count=7,
        min_history=100,
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave7.py",),
        provenance=(
            "POWER_LOTTO cross-lottery port of BIG_LOTTO strategy "
            "legacy_biglotto__verify_gemini_phase2_claim__6407a8f39519 "
            f"(donor archive {_DONOR_SHA256}); seven frozen, independent "
            "method tickets in fixed claim order."
        ),
        _predictor=_gemini_phase2_tickets,
    ),
)

WAVE3_BLOCKED_STRATEGIES: tuple[P638BlockedStrategy, ...] = (
    P638BlockedStrategy(
        strategy_id="biglotto_social_wisdom_anti_popularity",
        reason=(
            "BIGLOTTO_RULE_DEPENDENT: _unpopular_scores() hardcodes a "
            "Taiwan-lottery 'birthday-number' cultural banding table "
            "(1..31 penalized as birthday-plausible, specific bonus bands "
            "at 42..49) with no principled POWER_LOTTO 1..38 analog; this "
            "is domain numerology, not a pool/pick constant."
        ),
        source_paths=("src/lottolab/strategies/adapters/biglotto_selected.py",),
    ),
    P638BlockedStrategy(
        strategy_id="legacy_biglotto__predict_biglotto_echo_phase2__51c44b5c13d4",
        reason=(
            "BIGLOTTO_RULE_DEPENDENT: structural fitness embeds pool-49 magic "
            "sum/spread thresholds and fixed 1-16/17-33/34-49 zones; no "
            "authoritative P638 calibration exists."
        ),
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave1.py",),
    ),
    P638BlockedStrategy(
        strategy_id="legacy_biglotto__auto_discovery_biglotto__06bcb164db84",
        reason=(
            "BIGLOTTO_RULE_DEPENDENT: the 54-ticket discovery grid contains "
            "fixed pool-49 sum, structure, and numeric-zone calibrations; "
            "partial migration would change the strategy identity."
        ),
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave2.py",),
    ),
    P638BlockedStrategy(
        strategy_id="legacy_biglotto__test_ces__78d17c530ab8",
        reason=(
            "BIGLOTTO_RULE_DEPENDENT: CES validates fixed sums 110..190 and "
            "spread >=25, calibrations tied to the 1..49 domain."
        ),
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave8.py",),
    ),
    P638BlockedStrategy(
        strategy_id="legacy_biglotto__test_greedy_optimizer__82df7f878ece",
        reason=(
            "BIGLOTTO_RULE_DEPENDENT: greedy score targets sum 150 with a "
            "fixed 50-point scale and other pool-49 structural constants."
        ),
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave8.py",),
    ),
    P638BlockedStrategy(
        strategy_id="legacy_biglotto__social_wisdom_predictor__a00829b5d875",
        reason=(
            "BIGLOTTO_RULE_DEPENDENT: birthday-number cultural banding and "
            "pool-49 bonus bands have no P638 rule-contract analog."
        ),
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave12.py",),
    ),
    P638BlockedStrategy(
        strategy_id="legacy_biglotto__negative_selection_biglotto__98f860c52cc2",
        reason=(
            "BIGLOTTO_RULE_DEPENDENT: candidate generation and structural "
            "filtering embed pool-49 sum/spread/zone thresholds."
        ),
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave12.py",),
    ),
    P638BlockedStrategy(
        strategy_id="legacy_biglotto__test_cluster_cover__5b43959e7c55",
        reason=(
            "BLOCKED_SOURCE_CLOSURE: the donor's fixed three-ticket contract "
            "can exhaust its top-18 pool before every round-robin ticket "
            "reaches six numbers. The closure is non-prefix and frequent "
            "under P638 GameSpec validation; padding would invent a branch."
        ),
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave9.py",),
    ),
    P638BlockedStrategy(
        strategy_id="legacy_biglotto__test_4bet_dcb__3c7e3e661ad8",
        reason=(
            "BLOCKED_SOURCE_CLOSURE: the donor's fourth [12:18] slice is "
            "short whenever the correlation-boosted union has fewer than "
            "18 candidates. The closure is non-prefix; padding would invent "
            "a missing fallback."
        ),
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave13.py",),
    ),
    P638BlockedStrategy(
        strategy_id="legacy_biglotto__biglotto_3bet_optimizer__2835d6cb20c5",
        reason=(
            "BLOCKED_SOURCE_CLOSURE: at official P638 target 97000035 "
            "(cutoff 97000034), the donor-weighted candidate union has only "
            "13 numbers, so its third [8:14] slice is short. The donor has no "
            "fallback; padding would invent behavior."
        ),
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave4.py",),
    ),
    P638BlockedStrategy(
        strategy_id="legacy_biglotto__predict_biglotto_6bets_cluster__1fd9e8a7ae2a",
        reason=(
            "BLOCKED_SOURCE_CLOSURE: legal low-diversity P638 histories can "
            "supply too few distinct centers or companions for all six donor "
            "tickets. The donor has no total fallback; padding would invent "
            "behavior."
        ),
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave5.py",),
    ),
    P638BlockedStrategy(
        strategy_id="legacy_biglotto__predict_biglotto_7bets_cluster__8f55b5d94669",
        reason=(
            "BLOCKED_SOURCE_CLOSURE: legal low-diversity P638 histories can "
            "supply too few distinct centers or companions for all seven "
            "donor tickets. The donor has no total fallback; padding would "
            "invent behavior."
        ),
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave5.py",),
    ),
    P638BlockedStrategy(
        strategy_id="legacy_biglotto__backtest_strategy_1__41ed79a6de62",
        reason=(
            "BLOCKED_SOURCE_CLOSURE: on legal low-diversity P638 histories, "
            "the donor danger filter can remove the entire observed support, "
            "leaving its first ticket short. The donor has no refill branch."
        ),
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave10.py",),
    ),
    P638BlockedStrategy(
        strategy_id="legacy_biglotto__test_dcb__c3299c25ca59",
        reason=(
            "BLOCKED_SOURCE_CLOSURE: legal P638 histories can produce a "
            "correlation-boosted candidate union shorter than 14, making the "
            "donor's third [8:14] slice short. No donor fallback exists."
        ),
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave13.py",),
    ),
    P638BlockedStrategy(
        strategy_id="legacy_biglotto__test_ecp__c9d5ac6decdd",
        reason=(
            "BLOCKED_SOURCE_CLOSURE: at official P638 target 97000035 "
            "(cutoff 97000034), the donor consensus union has only 13 numbers, "
            "so its third [8:14] slice is short. No donor fallback exists."
        ),
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave14.py",),
    ),
    P638BlockedStrategy(
        strategy_id="legacy_biglotto__test_pce__9c0cf22b4217",
        reason=(
            "BLOCKED_SOURCE_CLOSURE: the donor intentionally returns up to "
            "three distinct consensus tickets, and legal P638 histories yield "
            "zero to two. Padding would invent a missing donor branch."
        ),
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave14.py",),
    ),
    P638BlockedStrategy(
        strategy_id="legacy_biglotto__quick_ml_predict__8b7ba0b52e2d",
        reason=(
            "BLOCKED_DEPENDENCY_OR_NONDETERMINISM: the frozen donor's "
            "off-by-one branch fails for essentially every eligible history; "
            "the task forbids inventing or repairing its missing branch."
        ),
        source_paths=("src/lottolab/strategies/adapters/biglotto_wave12.py",),
    ),
)

WAVE3_STRATEGY_BY_ID = {spec.strategy_id: spec for spec in WAVE3_STRATEGIES}

__all__ = [
    "WAVE3_BLOCKED_STRATEGIES",
    "WAVE3_STRATEGIES",
    "WAVE3_STRATEGY_BY_ID",
]
