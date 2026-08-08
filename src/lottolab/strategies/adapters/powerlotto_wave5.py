"""Exhaustive cross-lottery P638 ports, Wave 5 (remaining 11 families).

This module closes the Owner-authorized portable denominator with the DMS,
MWSC, CAG/Cluster/ZDP, Wave 10/11 seeded portfolios, and Wave 13/14
consensus families.  Pool and zone math is derived from the P638 GameSpec;
donor-declared seed material, method ordering, slices, and native positional
duplicates are preserved.  P638 second-zone logic remains exclusively in
``P638StrategySpec``.
"""

from __future__ import annotations

import hashlib
import heapq
import math
import random
from collections import Counter, defaultdict
from collections.abc import Callable
from itertools import combinations, count
from typing import Final

from lottolab.strategies.adapters.powerlotto_biglotto_core import (
    MAXIMUM,
    MINIMUM,
    PICK_COUNT,
    bayesian_ticket,
    deviation_ticket,
    frequency_ticket,
    hot_cold_mix_ticket,
    kill_numbers,
    markov_ticket,
    repeat_booster_ticket,
    statistical_ticket,
    ticket,
    trend_ticket,
    weighted_candidates,
    zone_balance_ticket,
)
from lottolab.strategies.adapters.powerlotto_wave1 import (
    P638FirstZoneTicketSet,
    P638HistoryRow,
    P638StrategySpec,
)

_DONOR_SHA256: Final = "a867d33c130daa8de00363df5ee52ca926385a8ef2c17f03b161a8b6726adf43"
type _Predictor = Callable[[tuple[P638HistoryRow, ...]], P638FirstZoneTicketSet]
type _TicketPredictor = Callable[[tuple[P638HistoryRow, ...]], tuple[int, ...]]


def _engine_output(method: str, history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    methods: dict[str, _TicketPredictor] = {
        "frequency": frequency_ticket,
        "bayesian": bayesian_ticket,
        "markov": markov_ticket,
        "trend": trend_ticket,
        "deviation": deviation_ticket,
        "statistical": statistical_ticket,
        "zone_balance": zone_balance_ticket,
        "hot_cold_mix": hot_cold_mix_ticket,
    }
    return methods[method](history)


def _dms_3bet(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    method_order = (
        "frequency",
        "bayesian",
        "markov",
        "trend",
        "deviation",
        "statistical",
        "zone_balance",
        "hot_cold_mix",
    )
    performance: Counter[str] = Counter()
    for index in range(10, 30):
        offset = 30 - index
        actual = set(history[-offset].numbers)
        past = history[:-offset]
        for method in method_order:
            try:
                performance[method] += len(set(_engine_output(method, past)) & actual)
            except Exception:
                continue
    selected = [method for method, _score in performance.most_common(3)]
    rows: list[tuple[int, ...]] = []
    for method in selected:
        try:
            rows.append(_engine_output(method, history))
        except Exception:
            continue
    while len(rows) < 3:
        rows.append(statistical_ticket(history))
    return tuple(rows)


def _mwsc_3bet(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    consensus: Counter[int] = Counter()
    for window in (10, 20, 50, 100):
        sample = history[-window:]
        for method in ("statistical", "deviation", "markov"):
            try:
                consensus.update(_engine_output(method, sample))
            except Exception:
                continue
    killed = set(kill_numbers(history, 10))
    for number in killed:
        consensus[number] = -9999
    starts = (0, 4, 8)
    required_pool_size = max(start + PICK_COUNT for start in starts)
    pool = [number for number, _score in consensus.most_common(PICK_COUNT * 3)]
    pool.extend(
        number
        for number in range(MINIMUM, MAXIMUM + 1)
        if number not in killed and number not in pool
    )
    pool = pool[:required_pool_size]
    return tuple(ticket(pool[start : start + PICK_COUNT]) for start in starts)


def _diversified_top18(history: tuple[P638HistoryRow, ...]) -> list[int]:
    return weighted_candidates(
        (
            (deviation_ticket(history), 2.0),
            (markov_ticket(history), 1.5),
            (statistical_ticket(history), 1.0),
        ),
        limit=PICK_COUNT * 3,
        excluded=kill_numbers(history, 10),
    )


def _cooccurrence_matrix(
    history: tuple[P638HistoryRow, ...],
) -> defaultdict[int, Counter[int]]:
    matrix: defaultdict[int, Counter[int]] = defaultdict(Counter)
    for draw in history[-200:]:
        for left, right in combinations(draw.numbers, 2):
            matrix[left][right] += 1
            matrix[right][left] += 1
    return matrix


def _cag_3bet(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    top_18 = _diversified_top18(history)
    matrix = _cooccurrence_matrix(history)
    pool = set(top_18)
    rows: list[tuple[int, ...]] = []
    for anchor in top_18[:3]:
        companions = [
            (candidate, matrix[anchor][candidate]) for candidate in pool if candidate != anchor
        ]
        companions.sort(
            key=lambda entry: (entry[1], -top_18.index(entry[0])),
            reverse=True,
        )
        rows.append(ticket([anchor, *(entry[0] for entry in companions[: PICK_COUNT - 1])]))
    return tuple(rows)


def _zdp_3bet(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    top_30 = weighted_candidates(
        (
            (deviation_ticket(history), 1.5),
            (markov_ticket(history), 1.5),
            (statistical_ticket(history), 2.0),
        ),
        limit=30,
        excluded=kill_numbers(history, 10),
    )
    first_cut = MAXIMUM // 3
    second_cut = 2 * (MAXIMUM // 3)
    low = [number for number in top_30 if MINIMUM <= number <= first_cut]
    middle = [number for number in top_30 if first_cut < number <= second_cut]
    high = [number for number in top_30 if second_cut < number <= MAXIMUM]
    rows: list[tuple[int, ...]] = []
    for heavy, others in ((low, middle + high), (middle, low + high), (high, low + middle)):
        rng = random.Random(42)
        row = list(heavy[:4])
        for number in others:
            if len(row) >= PICK_COUNT:
                break
            if number not in row:
                row.append(number)
        while len(row) < PICK_COUNT:
            row.append(rng.randint(MINIMUM, MAXIMUM))
        rows.append(ticket(row))
    return tuple(rows)


def _ordered_zone_balance(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    sample = history
    if len(sample) > 1 and sample[0].draw > sample[-1].draw:
        sample = tuple(reversed(sample))
    return zone_balance_ticket(sample)


def _bayesian_desc_ticket(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    total_draws = len(history)
    long_term = Counter(number for draw in history for number in draw.numbers)
    recent = history[:20] if total_draws > 20 else history
    recent_frequency = Counter(number for draw in recent for number in draw.numbers)
    if len(recent) < 5:
        stability = 0.5
    else:
        values = list(Counter(number for draw in recent for number in draw.numbers).values())
        if len(values) < 2:
            stability = 0.5
        else:
            mean = sum(values) / len(values)
            variance = sum((value - mean) ** 2 for value in values) / len(values)
            stability = 0.5 if mean == 0 else 1 / (1 + math.sqrt(variance) / mean)
    if total_draws < 50:
        likelihood_weight, prior_weight = 0.75, 0.25
    elif total_draws < 100:
        likelihood_weight, prior_weight = (0.65, 0.35) if stability > 0.7 else (0.55, 0.45)
    else:
        likelihood_weight, prior_weight = (0.6, 0.4) if stability > 0.7 else (0.5, 0.5)
    scores: dict[int, float] = {}
    for number in range(MINIMUM, MAXIMUM + 1):
        prior = long_term.get(number, 0) / (total_draws * PICK_COUNT)
        if prior == 0:
            prior = 1 / (total_draws * PICK_COUNT * 10)
        likelihood = recent_frequency.get(number, 0) / len(recent)
        scores[number] = likelihood * likelihood_weight + prior * prior_weight
    return ticket(sorted(scores, key=lambda number: scores[number], reverse=True)[:PICK_COUNT])


def _negative_excluded(history_desc: tuple[P638HistoryRow, ...]) -> set[int]:
    cold_frequency = Counter(
        number for draw in history_desc[: min(100, len(history_desc))] for number in draw.numbers
    )
    counts = [(number, cold_frequency.get(number, 0)) for number in range(MINIMUM, MAXIMUM + 1)]
    counts.sort(key=lambda item: item[1])
    cold = {number for number, _value in counts[: int(MAXIMUM * 20 / 100)]}
    last_seen = {number: 9999 for number in range(MINIMUM, MAXIMUM + 1)}
    for index, draw in enumerate(history_desc[: min(50, len(history_desc))]):
        for number in draw.numbers:
            if last_seen[number] > index:
                last_seen[number] = index
    overdue = {number for number, gap in last_seen.items() if gap >= 15}
    recent_frequency = Counter(number for draw in history_desc[:20] for number in draw.numbers)
    recent_cold = {
        number for number in range(MINIMUM, MAXIMUM + 1) if recent_frequency.get(number, 0) < 2
    }
    return (cold & overdue) | (cold & recent_cold)


def _filter_prediction(
    prediction: tuple[int, ...],
    excluded: set[int],
    history_desc: tuple[P638HistoryRow, ...],
) -> tuple[int, ...]:
    frequency = Counter(number for draw in history_desc[:50] for number in draw.numbers)
    available = [
        number
        for number in range(MINIMUM, MAXIMUM + 1)
        if number not in excluded and number not in prediction
    ]
    available.sort(key=lambda number: -frequency.get(number, 0))
    replacements = iter(available)
    result: list[int] = []
    for number in prediction:
        if number in excluded:
            result.append(next(replacements, number))
        else:
            result.append(number)
    return ticket(sorted(set(result))[: len(prediction)])


def _enhanced_dual_2bet(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    history_desc = tuple(reversed(history))
    excluded = _negative_excluded(history_desc)
    first = _ordered_zone_balance(history[-500:])
    second = _bayesian_desc_ticket(history[-300:])
    if excluded:
        first = _filter_prediction(first, excluded, history_desc)
        second = _filter_prediction(second, excluded, history_desc)
    return (ticket(first), ticket(second))


def _ac_value(numbers: tuple[int, ...]) -> int:
    differences = {
        right - left
        for index, left in enumerate(sorted(numbers))
        for right in sorted(numbers)[index + 1 :]
    }
    return len(differences) - (len(numbers) - 1)


def _entropy(numbers: tuple[int, ...]) -> float:
    ordered = sorted(numbers)
    gaps = [
        ordered[0],
        *[ordered[i + 1] - ordered[i] for i in range(len(ordered) - 1)],
        MAXIMUM - ordered[-1],
    ]
    total = sum(gaps)
    return -sum((gap / total) * math.log2(gap / total) for gap in gaps if gap > 0)


def _structural_stats(history: tuple[P638HistoryRow, ...]) -> dict[str, float]:
    rows = history[-100:]
    ac_values = [_ac_value(row.numbers) for row in rows]
    entropy_values = [_entropy(row.numbers) for row in rows]
    ac_average = sum(ac_values) / len(ac_values)
    entropy_average = sum(entropy_values) / len(entropy_values)
    return {
        "ac_avg": ac_average,
        "ac_std": math.sqrt(sum((value - ac_average) ** 2 for value in ac_values) / len(ac_values)),
        "entropy_avg": entropy_average,
        "entropy_std": math.sqrt(
            sum((value - entropy_average) ** 2 for value in entropy_values) / len(entropy_values)
        ),
    }


def _valid_structure(row: tuple[int, ...], stats: dict[str, float]) -> bool:
    return not (
        _ac_value(row) < stats["ac_avg"] - 1.5 * stats["ac_std"]
        or _entropy(row) < stats["entropy_avg"] - 1.5 * stats["entropy_std"]
    )


def _graph_adjacency(
    history: tuple[P638HistoryRow, ...], lookback: int = 500
) -> dict[int, dict[int, float]]:
    recent = history[-lookback:] if len(history) > lookback else history
    pair_frequency: Counter[tuple[int, int]] = Counter()
    for draw in recent:
        pair_frequency.update(combinations(draw.numbers, 2))
    threshold = max(2, len(recent) * 0.01)
    result: dict[int, dict[int, float]] = {number: {} for number in range(MINIMUM, MAXIMUM + 1)}
    for (left, right), value in pair_frequency.items():
        if value >= threshold:
            weight = value / len(recent)
            result[left][right] = weight
            result[right][left] = weight
    return result


def _betweenness(nodes: list[int], adjacency: dict[int, dict[int, float]]) -> dict[int, float]:
    values = dict.fromkeys(nodes, 0.0)
    for source in nodes:
        stack: list[int] = []
        predecessors: dict[int, list[int]] = {node: [] for node in nodes}
        sigma = dict.fromkeys(nodes, 0.0)
        sigma[source] = 1.0
        distance: dict[int, float] = {}
        seen = {source: 0.0}
        sequence = count()
        queue: list[tuple[float, int, int, int]] = [(0.0, next(sequence), source, source)]
        while queue:
            current_distance, _, predecessor, node = heapq.heappop(queue)
            if node in distance:
                continue
            sigma[node] += sigma[predecessor]
            stack.append(node)
            distance[node] = current_distance
            for neighbor, weight in adjacency.get(node, {}).items():
                candidate_distance = current_distance + weight
                if neighbor not in distance and (
                    neighbor not in seen or candidate_distance < seen[neighbor]
                ):
                    seen[neighbor] = candidate_distance
                    heapq.heappush(
                        queue,
                        (candidate_distance, next(sequence), node, neighbor),
                    )
                    sigma[neighbor] = 0.0
                    predecessors[neighbor] = [node]
                elif candidate_distance == seen[neighbor]:
                    sigma[neighbor] += sigma[node]
                    predecessors[neighbor].append(node)
        delta = dict.fromkeys(stack, 0.0)
        while stack:
            node = stack.pop()
            coefficient = (1 + delta[node]) / sigma[node]
            for predecessor in predecessors[node]:
                delta[predecessor] += sigma[predecessor] * coefficient
            if node != source:
                values[node] += delta[node]
    if len(nodes) > 2:
        scale = 1.0 / ((len(nodes) - 1) * (len(nodes) - 2))
        values = {node: value * scale for node, value in values.items()}
    return values


def _v6_frequency(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    basic = Counter(number for draw in history for number in draw.numbers)
    theoretical = len(history) * PICK_COUNT / MAXIMUM
    gaps: dict[int, int] = {}
    for index, draw in enumerate(reversed(history)):
        for number in draw.numbers:
            gaps.setdefault(number, index)
    for number in range(MINIMUM, MAXIMUM + 1):
        gaps.setdefault(number, len(history))
    weighted: dict[int, float] = {}
    total_weight = 0.0
    for index, draw in enumerate(reversed(history[-200:])):
        for number in draw.numbers:
            ratio = basic.get(number, 0) / theoretical if theoretical else 0.0
            decay = (
                0.018
                if ratio > 1.3
                else 0.013
                if ratio > 1.1
                else 0.007
                if ratio < 0.7
                else 0.009
                if ratio < 0.9
                else 0.01
            )
            weight = math.exp(-decay * index)
            weighted[number] = weighted.get(number, 0.0) + weight
            total_weight += weight
    maximum_gap = max(gaps.values())
    scores = {
        number: 0.4
        * (weighted.get(number, 0.0) / (total_weight / MAXIMUM) if total_weight else 0.0)
        + 0.6 * (gaps[number] / maximum_gap if maximum_gap else 0.0)
        for number in range(MINIMUM, MAXIMUM + 1)
    }
    return ticket(sorted(scores, key=lambda number: scores[number], reverse=True)[:PICK_COUNT])


def _diversified_ensemble_v6(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    history = history[-1000:]
    rng = random.Random(42)
    stats = _structural_stats(history)
    pool_1 = sorted(set(_bayesian_desc_ticket(history)) | set(_v6_frequency(history)))
    first = ticket(pool_1[:PICK_COUNT])
    for _ in range(150):
        sample = ticket(rng.sample(pool_1, PICK_COUNT))
        if _valid_structure(sample, stats):
            first = sample
            break

    graph_input = history[:500] if len(history) > 500 else history
    adjacency = _graph_adjacency(graph_input)
    nodes = list(range(MINIMUM, MAXIMUM + 1))
    scale = 1.0 / (len(nodes) - 1)
    degree = {node: len(adjacency[node]) * scale for node in nodes}
    between = _betweenness(nodes, adjacency)
    centrality = {node: degree[node] * 0.7 + between[node] * 0.3 for node in nodes}
    pool_2 = [number for number, _score in sorted(centrality.items(), key=lambda item: -item[1])][
        :20
    ]
    second = ticket(pool_2[:PICK_COUNT])
    for _ in range(150):
        sample = ticket(rng.sample(pool_2, PICK_COUNT))
        if _valid_structure(sample, stats):
            second = sample
            break

    tails = Counter(number % 10 for draw in history[-100:] for number in draw.numbers)
    hot_tails = [tail for tail, _value in tails.most_common(5)]
    skewed = (
        sum(
            1
            for draw in history[-10:]
            if (odd_ratio := sum(number % 2 for number in draw.numbers) / PICK_COUNT) >= 0.8
            or odd_ratio <= 0.2
        )
        >= 2
    )
    target_odds = 5 if skewed else 3
    odds = [number for number in range(MINIMUM, MAXIMUM + 1) if number % 2]
    evens = [number for number in range(MINIMUM, MAXIMUM + 1) if not number % 2]
    pool_3 = [number for number in odds + evens if number % 10 in hot_tails]
    if len(pool_3) < 12:
        pool_3 = list(range(MINIMUM, MAXIMUM + 1))
    third = ticket(pool_3[:PICK_COUNT])
    for _ in range(200):
        sample = ticket(rng.sample(pool_3, PICK_COUNT))
        if sum(number % 2 for number in sample) >= target_odds and _valid_structure(sample, stats):
            third = sample
            break
    return (first, second, third)


_RANDOM_PROTOCOL = "legacy_random_native/cpython_mt19937_v1"
_RANDOM_USER_SEED = "biglotto-full-universe-random-native-v1"
_HISTORY_PROTOCOL = "legacy_history_native/v1"
_HISTORY_USER_SEED = "biglotto-full-universe-history-native-v1"


def _target_after_cutoff(history: tuple[P638HistoryRow, ...]) -> str:
    draw_ids = {row.draw for row in history}
    target = f"{history[-1].draw}:lottolab-wave11-next-target"
    while target in draw_ids:
        target = f"{target}:next"
    return target


def _seed_integer(
    history: tuple[P638HistoryRow, ...],
    protocol: str,
    method_id: str,
    source_sha256: str,
    user_seed: str,
) -> int:
    material = "|".join(
        (protocol, method_id, source_sha256, _target_after_cutoff(history), "0", user_seed)
    )
    return int(hashlib.sha256(material.encode("utf-8")).hexdigest(), 16)


def _random_core_satellite(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    seed = _seed_integer(
        history,
        _RANDOM_PROTOCOL,
        "lottery_api/models/core_satellite.py",
        "611284461323dbbca0b5959498bf3f0e86bfaa35c4b902fdb64aabfe5076a6e2",
        _RANDOM_USER_SEED,
    )
    rng = random.Random()
    rng.seed(seed, version=2)
    pool = list(range(MINIMUM, MAXIMUM + 1))
    rng.shuffle(pool)
    core = sorted(pool[:2])
    satellites = pool[2:]
    satellite_count = PICK_COUNT - len(core)
    return tuple(
        ticket(core + satellites[index * satellite_count : (index + 1) * satellite_count])
        for index in range(3)
    )


def _random_zone_split(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    seed = _seed_integer(
        history,
        _RANDOM_PROTOCOL,
        "lottery_api/models/zone_split.py",
        "b6144f9d479feded3746d81e0d5682e7cfb28ba8d8aa03ff65f3706649996211",
        _RANDOM_USER_SEED,
    )
    rng = random.Random()
    rng.seed(seed, version=2)
    zone_size = (MAXIMUM - MINIMUM + 1) // 3
    rows: list[tuple[int, ...]] = []
    for index in range(3):
        start = MINIMUM + index * zone_size
        end = MAXIMUM if index == 2 else MINIMUM + (index + 1) * zone_size - 1
        pool = list(range(max(MINIMUM, start - 2), min(MAXIMUM, end + 2) + 1))
        rows.append(ticket(rng.sample(pool, PICK_COUNT)))
    return tuple(rows)


def _exhaustive_audit_3bet(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    seed = _seed_integer(
        history,
        _HISTORY_PROTOCOL,
        "tools/big_lotto_exhaustive_audit.py",
        "694d353b7ca230af6a860f5ef8977fdecbab031a30ad4e6c51b3d0c0f98b910c",
        _HISTORY_USER_SEED,
    )
    frequency = Counter(number for draw in history[-50:] for number in draw.numbers)
    ranked = sorted(
        range(MINIMUM, MAXIMUM + 1),
        key=lambda number: frequency.get(number, 0),
        reverse=True,
    )
    rng = random.Random()
    rng.seed(seed, version=2)
    hot, cold = rng.sample(ranked[:15], PICK_COUNT), rng.sample(ranked[-15:], PICK_COUNT)
    used = set(hot) | set(cold)
    orthogonal = rng.sample(
        [number for number in range(MINIMUM, MAXIMUM + 1) if number not in used],
        PICK_COUNT,
    )
    return (ticket(hot), ticket(cold), ticket(orthogonal))


def _asm_3bet(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    top = _diversified_top18(history)
    first_indexes = tuple(range(PICK_COUNT))
    second_indexes = (*range(0, 2), *range(PICK_COUNT, 2 * PICK_COUNT - 2))
    third_indexes = (
        *range(2, min(5, PICK_COUNT)),
        *range(2 * PICK_COUNT - 2, 2 * PICK_COUNT - 2 + PICK_COUNT - 3),
    )
    return tuple(
        ticket([top[index] for index in indexes])
        for indexes in (first_indexes, second_indexes, third_indexes)
    )


def _apply_zdp(candidates: list[int]) -> tuple[int, ...]:
    first_cut = MAXIMUM // 3
    second_cut = 2 * (MAXIMUM // 3)
    zones = {
        "low": (MINIMUM, first_cut),
        "mid": (first_cut + 1, second_cut),
        "high": (second_cut + 1, MAXIMUM),
    }
    high_maximum = 2 if MAXIMUM - second_cut < 10 else 3
    selected: list[int] = []
    counts: Counter[str] = Counter()
    for number in candidates:
        if len(selected) >= PICK_COUNT:
            break
        target = next(
            (name for name, (start, end) in zones.items() if start <= number <= end),
            None,
        )
        maximum = high_maximum if target == "high" else 3
        if target is None or counts[target] < maximum:
            selected.append(number)
            if target is not None:
                counts[target] += 1
    if len(selected) < PICK_COUNT:
        selected.extend(number for number in candidates if number not in selected)
    return ticket(selected[:PICK_COUNT])


def _hpsb_1bet(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    methods: tuple[tuple[str, _TicketPredictor], ...] = (
        ("hot_cold_mix", hot_cold_mix_ticket),
        ("markov", markov_ticket),
        ("deviation", deviation_ticket),
        ("trend", trend_ticket),
        ("statistical", statistical_ticket),
    )
    if len(history) < 20:
        votes: defaultdict[int, float] = defaultdict(float)
        for predictor, weight in (
            (statistical_ticket, 1.5),
            (markov_ticket, 2.0),
            (repeat_booster_ticket, 1.2),
            (bayesian_ticket, 1.5),
            (hot_cold_mix_ticket, 1.2),
            (deviation_ticket, 0.8),
        ):
            try:
                for rank, number in enumerate(predictor(history)):
                    votes[number] += weight * (0.8 + 0.2 * ((PICK_COUNT - rank) / PICK_COUNT))
            except ValueError:
                continue
        candidates = sorted(votes, key=lambda number: votes[number], reverse=True)
        return (_apply_zdp(candidates),)
    performance: Counter[str] = Counter()
    for name, predictor in methods:
        for offset in range(15):
            index = len(history) - 15 + offset
            if index <= 0:
                continue
            try:
                if len(set(predictor(history[:index])) & set(history[index].numbers)) >= 3:
                    performance[name] += 1
            except ValueError:
                continue
    chosen_name = performance.most_common(1)[0][0] if performance else "hot_cold_mix"
    methods_by_name: dict[str, _TicketPredictor] = dict(methods)
    chosen = methods_by_name[chosen_name]
    return (_apply_zdp(list(chosen(history))),)


def _spec(
    strategy_id: str,
    count_value: int,
    minimum_history: int,
    donor_id: str,
    source_path: str,
    predictor: _Predictor,
) -> P638StrategySpec:
    return P638StrategySpec(
        strategy_id=strategy_id,
        strategy_version="v0.1-p638-wave5",
        native_ticket_count=count_value,
        min_history=minimum_history,
        source_paths=(source_path,),
        provenance=(
            f"Exhaustive POWER_LOTTO GameSpec port of {donor_id}; donor archive "
            f"{_DONOR_SHA256}; native order and frozen random protocol preserved."
        ),
        _predictor=predictor,
    )


WAVE5_STRATEGIES: tuple[P638StrategySpec, ...] = (
    _spec(
        "power_biglotto_dms_3bet",
        3,
        20,
        "legacy_biglotto__test_dms__b63442289bd5",
        "src/lottolab/strategies/adapters/biglotto_wave8.py",
        _dms_3bet,
    ),
    _spec(
        "power_biglotto_mwsc_3bet",
        3,
        1,
        "legacy_biglotto__test_mwsc__ba37643d6a3b",
        "src/lottolab/strategies/adapters/biglotto_wave8.py",
        _mwsc_3bet,
    ),
    _spec(
        "power_biglotto_cag_3bet",
        3,
        1,
        "legacy_biglotto__test_cag__7ca5343dfedd",
        "src/lottolab/strategies/adapters/biglotto_wave9.py",
        _cag_3bet,
    ),
    _spec(
        "power_biglotto_zdp_3bet",
        3,
        1,
        "legacy_biglotto__test_zdp__e80cc7e95453",
        "src/lottolab/strategies/adapters/biglotto_wave9.py",
        _zdp_3bet,
    ),
    _spec(
        "power_biglotto_enhanced_dual_2bet",
        2,
        100,
        "legacy_biglotto__enhanced_dual_bet_predictor__d5b3de348d01",
        "src/lottolab/strategies/adapters/biglotto_wave10.py",
        _enhanced_dual_2bet,
    ),
    _spec(
        "power_biglotto_diversified_ensemble_v6_3bet",
        3,
        1,
        "legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d",
        "src/lottolab/strategies/adapters/biglotto_wave10.py",
        _diversified_ensemble_v6,
    ),
    _spec(
        "power_biglotto_random_core_satellite_3bet",
        3,
        1,
        "legacy_biglotto__core_satellite__611284461323",
        "src/lottolab/strategies/adapters/biglotto_wave11.py",
        _random_core_satellite,
    ),
    _spec(
        "power_biglotto_random_zone_split_3bet",
        3,
        1,
        "legacy_biglotto__zone_split__b6144f9d479f",
        "src/lottolab/strategies/adapters/biglotto_wave11.py",
        _random_zone_split,
    ),
    _spec(
        "power_biglotto_exhaustive_audit_3bet",
        3,
        50,
        "legacy_biglotto__big_lotto_exhaustive_audit__694d353b7ca2",
        "src/lottolab/strategies/adapters/biglotto_wave11.py",
        _exhaustive_audit_3bet,
    ),
    _spec(
        "power_biglotto_asm_3bet",
        3,
        1,
        "legacy_biglotto__test_asm__d39a233a4c75",
        "src/lottolab/strategies/adapters/biglotto_wave13.py",
        _asm_3bet,
    ),
    _spec(
        "power_biglotto_hpsb_1bet",
        1,
        1,
        "legacy_biglotto__hpsb_optimizer__cf5cd7d971e8",
        "src/lottolab/strategies/adapters/biglotto_wave14.py",
        _hpsb_1bet,
    ),
)

WAVE5_STRATEGY_BY_ID = {spec.strategy_id: spec for spec in WAVE5_STRATEGIES}

__all__ = ["WAVE5_STRATEGIES", "WAVE5_STRATEGY_BY_ID"]
