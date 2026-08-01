"""BigLotto native-strategy wave 2: thin ports of frozen legacy BACKTESTED methods.

Each adapter below is a direct, dependency-free port of one frozen legacy
source file (donor commit ``49a25effa62fc24f40789c16be6f11bdfb41a4a9``, the
same frozen snapshot as wave 1; see each class's ``provenance`` in
``strategies/catalog.py`` for the exact path/hash). Where the donor used
numpy only for scalar math with an exact, order-independent pure-Python
equivalent (``math.exp``, ``math.log2``, integer ``Counter`` frequency
tallies), this port uses the stdlib equivalent instead so this module has
zero new dependencies. No algorithm was changed, tuned, or "improved"
during the port.

Two donor families considered for wave 2 were rejected during verification,
not merely skipped: methods whose donor ranks candidates with
``numpy.argsort``/``numpy.sort`` were excluded because that default
(unstable) sort's tie-break order cannot be reproduced bit-for-bit by a
pure-Python stable ``sorted()`` -- ties are common, not rare, once several
candidate numbers share identical component scores. Methods whose donor
ranks candidates via ``scipy.fft``/``numpy.fft`` were excluded because a
pure-Python DFT does not reproduce FFT output bit-for-bit (empirically
confirmed: 100% mismatch rate, up to ~2e-12 absolute error, across sample
window sizes) -- floating-point summation order is not associative.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Callable
from itertools import combinations

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    PortfolioBetAdapter,
)

_MAX_NUM = 49
_PICK = 6


# ─── legacy_biglotto__high_prize_trend_optimizer__0fc72409150e ──────────────
# Donor: ai_lab/scripts/high_prize_trend_optimizer.py —
# HighPrizeTrendOptimizer.predict, swept across the file's own 7 declared
# lambda values (the exact sweep the donor's own test_lambda_values() runs),
# flattened in that declared order -- a 7-native-ticket portfolio.

_HIGH_PRIZE_TREND_LAMBDAS = (0.01, 0.02, 0.03, 0.05, 0.07, 0.10, 0.15)


def _high_prize_trend_predict(
    history: tuple[CausalDrawRow, ...], lambda_val: float
) -> tuple[int, ...]:
    weighted_freq: dict[int, float] = {}
    for age, draw in enumerate(reversed(history)):
        weight = math.exp(-lambda_val * age)
        for num in draw.numbers:
            weighted_freq[num] = weighted_freq.get(num, 0.0) + weight
    total = sum(weighted_freq.values())
    probs = [(n, weighted_freq.get(n, 0.0) / total) for n in range(1, _MAX_NUM + 1)]
    ranked = sorted(probs, key=lambda item: item[1], reverse=True)
    return tuple(sorted(n for n, _ in ranked[:_PICK]))


class BigLottoHighPrizeTrendAdapter(PortfolioBetAdapter):
    """Recency-weighted (exponential decay) frequency predictor swept across
    7 frozen lambda configurations -- one native ticket per lambda."""

    strategy_id = "legacy_biglotto__high_prize_trend_optimizer__0fc72409150e"
    strategy_name = "大樂透 High Prize Trend（7組Lambda衰減）"  # noqa: RUF001
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 7

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return tuple(_high_prize_trend_predict(history, lam) for lam in _HIGH_PRIZE_TREND_LAMBDAS)


# ─── legacy_biglotto__core_satellite__2e82891003b3 ──────────────────────────
# Donor: lottery_api/engine/core_satellite.py —
# CoreSatelliteGenerator.generate_from_history, swept across the file's own
# 4 documented history modes ('mid_frequency', 'hot', 'cold', 'balanced',
# in the order the donor's own docstring lists them), each called with the
# function's own defaults (num_bets=3, num_anchors=3, window=30) -- a
# 12-native-ticket portfolio (4 modes x 3 bets).
#
# The donor's ``generate()`` falls back to ``random.shuffle``/
# ``random.sample`` only when the candidate pool is too small to cover
# num_anchors + num_bets*(pick_count-num_anchors) = 3 + 3*3 = 12 numbers.
# Every one of the 4 modes builds its pool from the full 49-number legal
# domain (each is a `sorted()` permutation of range(1, 50), and the
# 'balanced' interleave of two such permutations always covers all 49
# numbers by construction), so the pool always has 49 >= 12 members and
# those random branches are provably unreachable for this fixed
# configuration -- omitted here, not "improved away".

_CORE_SATELLITE_MODES = ("mid_frequency", "hot", "cold", "balanced")
_CORE_SATELLITE_NUM_BETS = 3
_CORE_SATELLITE_NUM_ANCHORS = 3
_CORE_SATELLITE_WINDOW = 30


def _core_satellite_pool(history: tuple[CausalDrawRow, ...], window: int, method: str) -> list[int]:
    recent = history[-window:]
    freq: Counter[int] = Counter()
    for draw in recent:
        for n in draw.numbers:
            if 1 <= n <= _MAX_NUM:
                freq[n] += 1
    all_nums = list(range(1, _MAX_NUM + 1))

    if method == "hot":
        return sorted(all_nums, key=lambda n: freq.get(n, 0), reverse=True)
    if method == "cold":
        return sorted(all_nums, key=lambda n: freq.get(n, 0))
    if method == "balanced":
        hot = sorted(all_nums, key=lambda n: freq.get(n, 0), reverse=True)
        cold = sorted(all_nums, key=lambda n: freq.get(n, 0))
        pool: list[int] = []
        for h, c in zip(hot, cold, strict=True):
            if h not in pool:
                pool.append(h)
            if c not in pool:
                pool.append(c)
        return pool
    # mid_frequency (the donor's default)
    expected = window * _PICK / _MAX_NUM
    return sorted(all_nums, key=lambda n: abs(freq.get(n, 0) - expected))


def _core_satellite_generate(
    pool: list[int], num_bets: int, num_anchors: int, pick_count: int
) -> tuple[tuple[int, ...], ...]:
    core_size = num_anchors
    sat_per_bet = pick_count - core_size
    filtered_pool = [n for n in pool if 1 <= n <= _MAX_NUM]
    anchors = filtered_pool[:core_size]
    anchor_set = set(anchors)
    sat_candidates = [n for n in filtered_pool if n not in anchor_set]

    bets: list[tuple[int, ...]] = []
    used: set[int] = set()
    for _ in range(num_bets):
        bet_sats: list[int] = []
        for n in sat_candidates:
            if n not in used and len(bet_sats) < sat_per_bet:
                bet_sats.append(n)
                used.add(n)
        bets.append(tuple(sorted(set(anchors) | set(bet_sats))))
    return tuple(bets)


class BigLottoCoreSatelliteAdapter(PortfolioBetAdapter):
    """Core-satellite anchored bet structure, swept across 4 frozen
    candidate-pool modes -- 3 native tickets per mode."""

    strategy_id = "legacy_biglotto__core_satellite__2e82891003b3"
    strategy_name = "大樂透 Core-Satellite（4模式x3注）"  # noqa: RUF001
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 12

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        tickets: list[tuple[int, ...]] = []
        for method in _CORE_SATELLITE_MODES:
            pool = _core_satellite_pool(history, _CORE_SATELLITE_WINDOW, method)
            tickets.extend(
                _core_satellite_generate(
                    pool, _CORE_SATELLITE_NUM_BETS, _CORE_SATELLITE_NUM_ANCHORS, _PICK
                )
            )
        return tuple(tickets)


# ─── legacy_biglotto__auto_discovery_biglotto__06bcb164db84 ────────────────
# Donor: tools/auto_discovery_biglotto.py — 30 frozen candidate functions
# (dimensions A-F), each swept across the file's own ``build_methods()``
# window-parameter grid, flattened in ``build_methods()``'s own dict
# insertion order -- a 54-native-ticket portfolio (15+11+7+7+6+8 = 54).
# Every function below is a literal, unmodified port: only ``d['numbers']``
# (donor dict draws) became ``draw.numbers`` (already-sorted CausalDrawRow
# tuples), and ``history[-window:]`` needs no length guard because tuple
# slicing already returns the whole tuple when window exceeds its length.
# ``structural_sum_regression``'s donor computes ``np.mean(sums)`` into a
# variable that is never read (superseded by its own EMA two lines later);
# that dead computation is omitted here since it cannot affect any output.


def _ad_cooccurrence_top_pairs(
    history: tuple[CausalDrawRow, ...], window: int = 100
) -> tuple[int, ...]:
    """A1: strongest pairwise co-occurrence, greedily assembled."""
    recent = history[-window:]
    pair_freq: Counter[tuple[int, int]] = Counter()
    for d in recent:
        nums = sorted(d.numbers[:_PICK])
        for p in combinations(nums, 2):
            pair_freq[p] += 1
    selected: set[int] = set()
    for (a, b), _ in pair_freq.most_common():
        if len(selected) >= _PICK:
            break
        if a not in selected and b not in selected and len(selected) <= _PICK - 2:
            selected.add(a)
            selected.add(b)
        elif a not in selected and len(selected) < _PICK:
            selected.add(a)
        elif b not in selected and len(selected) < _PICK:
            selected.add(b)
    return tuple(sorted(list(selected)[:_PICK]))


def _ad_cooccurrence_transition_pairs(
    history: tuple[CausalDrawRow, ...], window: int = 50
) -> tuple[int, ...]:
    """A2: prior-draw-pair -> this-draw-number transition frequency."""
    recent = history[-window:]
    pair_trans: Counter[tuple[tuple[int, int], int]] = Counter()
    for i in range(len(recent) - 1):
        prev_pairs = set(combinations(sorted(recent[i].numbers[:_PICK]), 2))
        next_nums = set(recent[i + 1].numbers[:_PICK])
        for pp in prev_pairs:
            for n in next_nums:
                pair_trans[(pp, n)] += 1
    last_pairs = set(combinations(sorted(history[-1].numbers[:_PICK]), 2))
    scores: Counter[int] = Counter()
    for pp in last_pairs:
        for n in range(1, _MAX_NUM + 1):
            scores[n] += pair_trans.get((pp, n), 0)
    return tuple(sorted(n for n, _ in sorted(scores.items(), key=lambda x: -x[1])[:_PICK]))


def _ad_cooccurrence_anti_pairs(
    history: tuple[CausalDrawRow, ...], window: int = 100
) -> tuple[int, ...]:
    """A3: least-co-occurring numbers (orthogonal coverage)."""
    recent = history[-window:]
    pair_freq: Counter[tuple[int, int]] = Counter()
    for d in recent:
        nums = sorted(d.numbers[:_PICK])
        for p in combinations(nums, 2):
            pair_freq[p] += 1
    num_cooc: Counter[int] = Counter()
    for (a, b), f in pair_freq.items():
        num_cooc[a] += f
        num_cooc[b] += f
    candidates = sorted(range(1, _MAX_NUM + 1), key=lambda x: num_cooc.get(x, 0))
    return tuple(sorted(candidates[:_PICK]))


def _ad_cooccurrence_triplet(
    history: tuple[CausalDrawRow, ...], window: int = 100
) -> tuple[int, ...]:
    """A4: triplet co-occurrence mining."""
    recent = history[-window:]
    trip_freq: Counter[tuple[int, int, int]] = Counter()
    for d in recent:
        nums = sorted(d.numbers[:_PICK])
        for t in combinations(nums, 3):
            trip_freq[t] += 1
    selected: set[int] = set()
    for trip, _ in trip_freq.most_common():
        if len(selected) >= _PICK:
            break
        for n in trip:
            if n not in selected and len(selected) < _PICK:
                selected.add(n)
    remaining = [n for n in range(1, _MAX_NUM + 1) if n not in selected]
    while len(selected) < _PICK:
        selected.add(remaining.pop(0))
    return tuple(sorted(list(selected)[:_PICK]))


def _ad_cooccurrence_conditional(
    history: tuple[CausalDrawRow, ...], window: int = 50
) -> tuple[int, ...]:
    """A5: conditional co-occurrence given the last draw's numbers."""
    recent = history[-window:]
    cond_cooc: Counter[int] = Counter()
    prev_nums = set(history[-1].numbers[:_PICK])
    for i in range(len(recent) - 1):
        curr = set(recent[i + 1].numbers[:_PICK])
        prev = set(recent[i].numbers[:_PICK])
        common_with_prev = prev & prev_nums
        if common_with_prev:
            for n in curr:
                cond_cooc[n] += len(common_with_prev)
    candidates = sorted(cond_cooc.items(), key=lambda x: -x[1])
    return tuple(sorted(n for n, _ in candidates[:_PICK]))


def _ad_classify_structure(nums: tuple[int, ...]) -> str:
    """Classify one draw's numbers into a (sum, odd/even, zone, consec) template."""
    sorted_nums = sorted(nums[:_PICK])
    s = sum(sorted_nums)
    odd = sum(1 for n in sorted_nums if n % 2 == 1)
    z1 = sum(1 for n in sorted_nums if n <= 16)
    z2 = sum(1 for n in sorted_nums if 17 <= n <= 33)
    z3 = sum(1 for n in sorted_nums if n >= 34)
    has_consec = any(sorted_nums[i + 1] - sorted_nums[i] == 1 for i in range(len(sorted_nums) - 1))

    sum_cat = "low" if s < 130 else "high" if s > 170 else "mid"
    oe_cat = f"{odd}o{6 - odd}e"
    zone_cat = f"{z1}-{z2}-{z3}"
    consec_cat = "C" if has_consec else "N"

    return f"{sum_cat}_{oe_cat}_{zone_cat}_{consec_cat}"


def _ad_structural_template_match(
    history: tuple[CausalDrawRow, ...], window: int = 200
) -> tuple[int, ...]:
    """B1: predict next structure template, select numbers matching its constraints."""
    recent = history[-window:]
    struct_seq = [_ad_classify_structure(d.numbers) for d in recent]
    trans: Counter[tuple[str, str]] = Counter()
    for i in range(len(struct_seq) - 1):
        trans[(struct_seq[i], struct_seq[i + 1])] += 1

    last_struct = _ad_classify_structure(history[-1].numbers)
    next_candidates = [(s2, cnt) for (s1, s2), cnt in trans.items() if s1 == last_struct]
    if not next_candidates:
        struct_freq = Counter(struct_seq)
        target_struct = struct_freq.most_common(1)[0][0]
    else:
        target_struct = max(next_candidates, key=lambda x: x[1])[0]

    parts = target_struct.split("_")
    zone_cat = parts[2]
    target_zones = [int(x) for x in zone_cat.split("-")]

    freq: Counter[int] = Counter(n for d in recent for n in d.numbers)
    zones = {
        0: sorted([(n, freq.get(n, 0)) for n in range(1, 17)], key=lambda x: -x[1]),
        1: sorted([(n, freq.get(n, 0)) for n in range(17, 34)], key=lambda x: -x[1]),
        2: sorted([(n, freq.get(n, 0)) for n in range(34, 50)], key=lambda x: -x[1]),
    }

    selected: list[int] = []
    for zi, count in enumerate(target_zones):
        zone_nums = [n for n, _ in zones[zi][: count * 2]]
        selected.extend(zone_nums[:count])

    if len(selected) < _PICK:
        remaining = [n for n in range(1, _MAX_NUM + 1) if n not in selected]
        remaining.sort(key=lambda x: -freq.get(x, 0))
        selected.extend(remaining[: _PICK - len(selected)])

    return tuple(sorted(selected[:_PICK]))


def _ad_structural_sum_regression(
    history: tuple[CausalDrawRow, ...], window: int = 50
) -> tuple[int, ...]:
    """B2: sum-value regression via EMA, greedily filled toward the target sum."""
    recent = history[-window:]
    sums = [sum(d.numbers[:_PICK]) for d in recent]
    ema = sums[0]
    alpha = 0.1
    for s in sums[1:]:
        ema = alpha * s + (1 - alpha) * ema
    target_sum = int(ema)

    freq: Counter[int] = Counter(n for d in recent for n in d.numbers)
    candidates = sorted(range(1, _MAX_NUM + 1), key=lambda x: -freq.get(x, 0))

    selected: list[int] = []
    for n in candidates:
        if len(selected) < _PICK:
            test_sum = sum(selected) + n
            remaining_slots = _PICK - len(selected) - 1
            if remaining_slots > 0:
                min_possible = test_sum + sum(range(1, remaining_slots + 1))
                max_possible = test_sum + sum(range(_MAX_NUM - remaining_slots + 1, _MAX_NUM + 1))
                if min_possible <= target_sum <= max_possible:
                    selected.append(n)
            else:
                selected.append(n)
    if len(selected) < _PICK:
        remaining = [n for n in range(1, _MAX_NUM + 1) if n not in selected]
        selected.extend(remaining[: _PICK - len(selected)])
    return tuple(sorted(selected[:_PICK]))


def _ad_structural_odd_even_transition(
    history: tuple[CausalDrawRow, ...], window: int = 100
) -> tuple[int, ...]:
    """B3: odd-count transition matrix."""
    recent = history[-window:]
    oe_seq = [sum(1 for n in d.numbers[:_PICK] if n % 2 == 1) for d in recent]
    trans: Counter[tuple[int, int]] = Counter()
    for i in range(len(oe_seq) - 1):
        trans[(oe_seq[i], oe_seq[i + 1])] += 1

    last_oe = oe_seq[-1]
    next_candidates = [(oe2, cnt) for (oe1, oe2), cnt in trans.items() if oe1 == last_oe]
    target_odd = max(next_candidates, key=lambda x: x[1])[0] if next_candidates else 3

    freq: Counter[int] = Counter(n for d in recent for n in d.numbers)
    odds = sorted(range(1, _MAX_NUM + 1, 2), key=lambda x: -freq.get(x, 0))
    evens = sorted(range(2, _MAX_NUM + 1, 2), key=lambda x: -freq.get(x, 0))

    selected = odds[:target_odd] + evens[: _PICK - target_odd]
    return tuple(sorted(selected[:_PICK]))


def _ad_structural_gap_pattern(
    history: tuple[CausalDrawRow, ...], window: int = 100
) -> tuple[int, ...]:
    """B4: match historical draws with a similar inter-number gap pattern."""
    recent = history[-window:]
    last_nums = sorted(history[-1].numbers[:_PICK])
    last_gaps = tuple(last_nums[i + 1] - last_nums[i] for i in range(len(last_nums) - 1))

    similar_next: list[tuple[int, ...]] = []
    for i in range(len(recent) - 1):
        nums = sorted(recent[i].numbers[:_PICK])
        gaps = tuple(nums[j + 1] - nums[j] for j in range(len(nums) - 1))
        dist = sum(abs(a - b) for a, b in zip(gaps, last_gaps, strict=True))
        if dist <= 10:
            similar_next.append(recent[i + 1].numbers[:_PICK])

    if similar_next:
        freq = Counter(n for nums in similar_next for n in nums)
        return tuple(sorted(n for n, _ in freq.most_common(_PICK)))
    freq = Counter(n for d in recent for n in d.numbers)
    return tuple(sorted(n for n, _ in freq.most_common(_PICK)))


def _ad_conditional_entropy_selector(
    history: tuple[CausalDrawRow, ...], window: int = 100
) -> tuple[int, ...]:
    """C1: lowest conditional-entropy (most predictable) numbers, ranked by
    their own predicted continuation probability."""
    recent = history[-window:]
    entropies: dict[int, float] = {}
    for n in range(1, _MAX_NUM + 1):
        seq = [1 if n in d.numbers else 0 for d in recent]
        counts = {"00": 0, "01": 0, "10": 0, "11": 0}
        for i in range(len(seq) - 1):
            key = f"{seq[i]}{seq[i + 1]}"
            counts[key] += 1
        total_0 = counts["00"] + counts["01"]
        total_1 = counts["10"] + counts["11"]
        h = 0.0
        for prev in (0, 1):
            total = total_0 if prev == 0 else total_1
            if total == 0:
                continue
            p_weight = total / (len(seq) - 1)
            for next_val in (0, 1):
                key = f"{prev}{next_val}"
                if counts[key] > 0:
                    p = counts[key] / total
                    h -= p_weight * p * math.log2(p + 1e-10)
        entropies[n] = h

    predictions: list[tuple[int, float, float]] = []
    for n in range(1, _MAX_NUM + 1):
        seq = [1 if n in d.numbers else 0 for d in recent]
        last_state = seq[-1]
        after_same = sum(1 for i in range(len(seq) - 1) if seq[i] == last_state and seq[i + 1] == 1)
        total_same = sum(1 for i in range(len(seq) - 1) if seq[i] == last_state)
        p_next = after_same / total_same if total_same > 0 else 0
        predictions.append((n, p_next, entropies[n]))

    predictions.sort(key=lambda x: (-x[1], x[2]))
    return tuple(sorted(n for n, _, _ in predictions[:_PICK]))


def _ad_mutual_information_selector(
    history: tuple[CausalDrawRow, ...], window: int = 100
) -> tuple[int, ...]:
    """C2: numbers with the highest mutual information against next-draw appearance."""
    recent = history[-window:]
    w = len(recent)

    vectors: dict[int, list[int]] = {
        n: [1 if n in d.numbers else 0 for d in recent] for n in range(1, _MAX_NUM + 1)
    }

    mi_scores: dict[int, tuple[float, float]] = {}
    for n in range(1, _MAX_NUM + 1):
        x = vectors[n][:-1]
        y = [1 if n in recent[i + 1].numbers else 0 for i in range(w - 1)]

        joint: Counter[tuple[int, int]] = Counter()
        for xi, yi in zip(x, y, strict=True):
            joint[(xi, yi)] += 1

        mi = 0.0
        total = len(x)
        px = Counter(x)
        py = Counter(y)

        for (xi, yi), count in joint.items():
            p_xy = count / total
            p_x = px[xi] / total
            p_y = py[yi] / total
            if p_xy > 0 and p_x > 0 and p_y > 0:
                mi += p_xy * math.log2(p_xy / (p_x * p_y) + 1e-10)

        last_state = vectors[n][-1]
        after = sum(
            1 for i in range(w - 1) if vectors[n][i] == last_state and n in recent[i + 1].numbers
        )
        total_after = sum(1 for i in range(w - 1) if vectors[n][i] == last_state)
        p_pred = after / total_after if total_after > 0 else 0

        mi_scores[n] = (mi, p_pred)

    scored = sorted(mi_scores.items(), key=lambda x: -(x[1][0] * x[1][1]))
    return tuple(sorted(n for n, _ in scored[:_PICK]))


def _ad_surprise_selector(history: tuple[CausalDrawRow, ...], window: int = 100) -> tuple[int, ...]:
    """C3: most self-information-surprising numbers seen recently (gap <= 5)."""
    recent = history[-window:]
    freq: Counter[int] = Counter(n for d in recent for n in d.numbers)
    total = sum(freq.values())
    surprises: dict[int, float] = {}
    for n in range(1, _MAX_NUM + 1):
        p = freq.get(n, 0.5) / total
        surprises[n] = -math.log2(p + 1e-10)

    last_seen: dict[int, int] = {}
    for i, d in enumerate(history):
        for n in d.numbers:
            last_seen[n] = i
    current = len(history)

    scored: list[tuple[int, float]] = []
    for n in range(1, _MAX_NUM + 1):
        gap = current - last_seen.get(n, 0)
        if gap <= 5:
            scored.append((n, surprises.get(n, 0)))
    scored.sort(key=lambda x: -x[1])
    result = [n for n, _ in scored[:_PICK]]
    if len(result) < _PICK:
        remaining = sorted(surprises.items(), key=lambda x: -x[1])
        for n, _ in remaining:
            if n not in result and len(result) < _PICK:
                result.append(n)
    return tuple(sorted(result[:_PICK]))


def _ad_negative_elimination(
    history: tuple[CausalDrawRow, ...], window: int = 100
) -> tuple[int, ...]:
    """D1: eliminate the least-likely numbers, keep the lowest kill score."""
    recent = history[-window:]
    freq: Counter[int] = Counter(n for d in recent for n in d.numbers)

    last_draw_numbers = history[-1].numbers
    prev_draw_numbers = history[-2].numbers if len(history) >= 2 else ()

    kill_scores: Counter[int] = Counter()
    for n in range(1, _MAX_NUM + 1):
        if freq.get(n, 0) > window * 6 / 49 * 1.5:
            kill_scores[n] += 2
        if n in last_draw_numbers:
            kill_scores[n] += 1
        if n in prev_draw_numbers and n in last_draw_numbers:
            kill_scores[n] += 2

    candidates = sorted(
        range(1, _MAX_NUM + 1), key=lambda x: (kill_scores.get(x, 0), -freq.get(x, 0))
    )
    return tuple(sorted(candidates[:_PICK]))


def _ad_negative_overdue_filter(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """D2: eliminate extreme-overdue and just-appeared numbers, keep moderate gaps."""
    last_seen: dict[int, int] = {}
    for i, d in enumerate(history):
        for n in d.numbers:
            last_seen[n] = i
    current = len(history)
    gaps = {n: current - last_seen.get(n, 0) for n in range(1, _MAX_NUM + 1)}
    gap_values = list(gaps.values())
    mean_gap = sum(gap_values) / len(gap_values)
    variance = sum((g - mean_gap) ** 2 for g in gap_values) / len(gap_values)
    std_gap = math.sqrt(variance)

    moderate = [(n, g) for n, g in gaps.items() if mean_gap - std_gap <= g <= mean_gap + std_gap]
    moderate.sort(key=lambda x: x[1])

    result = [n for n, _ in moderate[:_PICK]]
    if len(result) < _PICK:
        remaining = sorted(gaps.items(), key=lambda x: abs(x[1] - mean_gap))
        for n, _ in remaining:
            if n not in result and len(result) < _PICK:
                result.append(n)
    return tuple(sorted(result[:_PICK]))


def _ad_negative_consensus_remove(
    history: tuple[CausalDrawRow, ...], window: int = 30
) -> tuple[int, ...]:
    """D3: remove the top-10 consensus-hot numbers, keep the rest by frequency."""
    freq: Counter[int] = Counter(n for d in history[-window:] for n in d.numbers)
    ranked_hot = sorted(range(1, _MAX_NUM + 1), key=lambda x: -freq.get(x, 0))
    consensus = set(ranked_hot[:10])
    candidates = [(n, freq.get(n, 0)) for n in range(1, _MAX_NUM + 1) if n not in consensus]
    candidates.sort(key=lambda x: -x[1])
    return tuple(sorted(n for n, _ in candidates[:_PICK]))


def _ad_zone_transition_markov(
    history: tuple[CausalDrawRow, ...], window: int = 100
) -> tuple[int, ...]:
    """E1: Markov transition over (Z1, Z2, Z3) zone-count triples."""
    recent = history[-window:]
    zone_seq: list[tuple[int, int, int]] = []
    for d in recent:
        nums = d.numbers[:_PICK]
        z1 = sum(1 for n in nums if n <= 16)
        z2 = sum(1 for n in nums if 17 <= n <= 33)
        z3 = sum(1 for n in nums if n >= 34)
        zone_seq.append((z1, z2, z3))

    trans: Counter[tuple[tuple[int, int, int], tuple[int, int, int]]] = Counter()
    for i in range(len(zone_seq) - 1):
        trans[(zone_seq[i], zone_seq[i + 1])] += 1

    last_zone = zone_seq[-1]
    next_candidates = [(z2, cnt) for (z1, z2), cnt in trans.items() if z1 == last_zone]
    target_zone = max(next_candidates, key=lambda x: x[1])[0] if next_candidates else (2, 2, 2)

    freq: Counter[int] = Counter(n for d in recent for n in d.numbers)
    z_ranges = ((1, 17), (17, 34), (34, 50))
    selected: list[int] = []
    for zi, count in enumerate(target_zone):
        lo, hi = z_ranges[zi]
        zone_nums = sorted([(n, freq.get(n, 0)) for n in range(lo, hi)], key=lambda x: -x[1])
        selected.extend(n for n, _ in zone_nums[:count])

    if len(selected) < _PICK:
        remaining = [n for n in range(1, _MAX_NUM + 1) if n not in selected]
        remaining.sort(key=lambda x: -freq.get(x, 0))
        selected.extend(remaining[: _PICK - len(selected)])
    return tuple(sorted(selected[:_PICK]))


def _ad_zone_consecutive_zone_bet(
    history: tuple[CausalDrawRow, ...], window: int = 50
) -> tuple[int, ...]:
    """E2: allocate picks toward zones with more historical consecutive pairs."""
    recent = history[-window:]
    zone_consec: Counter[str] = Counter()
    for d in recent:
        nums = sorted(d.numbers[:_PICK])
        for i in range(len(nums) - 1):
            if nums[i + 1] - nums[i] == 1:
                if nums[i] <= 16:
                    zone_consec["Z1"] += 1
                elif nums[i] <= 33:
                    zone_consec["Z2"] += 1
                else:
                    zone_consec["Z3"] += 1

    total_c = sum(zone_consec.values()) or 1
    allocations = {
        "Z1": max(1, round(_PICK * zone_consec.get("Z1", 1) / total_c)),
        "Z2": max(1, round(_PICK * zone_consec.get("Z2", 1) / total_c)),
        "Z3": max(1, round(_PICK * zone_consec.get("Z3", 1) / total_c)),
    }
    while sum(allocations.values()) > _PICK:
        max_z = max(allocations, key=lambda k: allocations[k])
        allocations[max_z] -= 1
    while sum(allocations.values()) < _PICK:
        min_z = min(allocations, key=lambda k: allocations[k])
        allocations[min_z] += 1

    freq: Counter[int] = Counter(n for d in recent for n in d.numbers)
    z_ranges = {"Z1": (1, 17), "Z2": (17, 34), "Z3": (34, 50)}
    selected: list[int] = []
    for z, count in allocations.items():
        lo, hi = z_ranges[z]
        zone_nums = sorted([(n, freq.get(n, 0)) for n in range(lo, hi)], key=lambda x: -x[1])
        selected.extend(n for n, _ in zone_nums[:count])
    return tuple(sorted(selected[:_PICK]))


def _ad_graph_centrality_bet(
    history: tuple[CausalDrawRow, ...], window: int = 100
) -> tuple[int, ...]:
    """F1: highest degree-centrality numbers in the co-occurrence graph."""
    recent = history[-window:]
    degree: Counter[int] = Counter()
    for d in recent:
        nums = d.numbers[:_PICK]
        for a, b in combinations(sorted(nums), 2):
            degree[a] += 1
            degree[b] += 1
    return tuple(sorted(n for n, _ in degree.most_common(_PICK)))


def _ad_graph_bridge_bet(history: tuple[CausalDrawRow, ...], window: int = 100) -> tuple[int, ...]:
    """F2: highest bridge-score (betweenness-approximation) numbers."""
    recent = history[-window:]
    adj: defaultdict[int, Counter[int]] = defaultdict(Counter)
    for d in recent:
        nums = d.numbers[:_PICK]
        for a, b in combinations(sorted(nums), 2):
            adj[a][b] += 1
            adj[b][a] += 1

    # typeshed's Counter is hard-typed to int values; the donor's own
    # bridge_score is a Counter holding float ratios (used only for its
    # Counter-specific most_common() tie-break order, which is NOT the
    # same algorithm as sorted() -- see the module docstring on argsort).
    bridge_score: Counter[int] = Counter()
    for n in range(1, _MAX_NUM + 1):
        neighbors = set(adj[n].keys())
        non_edges = 0
        pairs = 0
        for a, b in combinations(neighbors, 2):
            pairs += 1
            if b not in adj[a]:
                non_edges += 1
        if pairs > 0:
            bridge_score[n] = non_edges / pairs  # pyright: ignore[reportArgumentType]
    return tuple(sorted(n for n, _ in bridge_score.most_common(_PICK)))


def _ad_graph_pagerank_bet(
    history: tuple[CausalDrawRow, ...],
    window: int = 100,
    damping: float = 0.85,
    iterations: int = 20,
) -> tuple[int, ...]:
    """F3: highest-PageRank numbers in the co-occurrence graph."""
    recent = history[-window:]
    adj: defaultdict[int, Counter[int]] = defaultdict(Counter)
    for d in recent:
        nums = d.numbers[:_PICK]
        for a, b in combinations(sorted(nums), 2):
            adj[a][b] += 1
            adj[b][a] += 1

    nodes = list(range(1, _MAX_NUM + 1))
    n_nodes = len(nodes)
    pr: dict[int, float] = dict.fromkeys(nodes, 1.0 / n_nodes)

    for _ in range(iterations):
        new_pr: dict[int, float] = {}
        for nd in nodes:
            neighbors = adj[nd]
            incoming = 0.0
            for neighbor, weight in neighbors.items():
                neighbor_total = sum(adj[neighbor].values())
                if neighbor_total > 0:
                    incoming += pr[neighbor] * weight / neighbor_total
            new_pr[nd] = (1 - damping) / n_nodes + damping * incoming
        pr = new_pr

    ranked = sorted(pr.items(), key=lambda x: -x[1])
    return tuple(sorted(n for n, _ in ranked[:_PICK]))


# ``build_methods()``'s own dict insertion order: dimension A through F, each
# method's own declared window sweep in the donor's own listed order.
# (name, callable, window) — window=None means the donor's own default
# (only D2, which the donor declares with no sweep at all).
_AutoDiscoveryFunc = Callable[..., tuple[int, ...]]
_AUTO_DISCOVERY_METHODS: tuple[tuple[str, _AutoDiscoveryFunc, int | None], ...] = (
    *((f"A1_cooc_pairs_w{w}", _ad_cooccurrence_top_pairs, w) for w in (30, 50, 100, 200)),
    *((f"A2_cooc_trans_w{w}", _ad_cooccurrence_transition_pairs, w) for w in (30, 50, 100)),
    *((f"A3_cooc_anti_w{w}", _ad_cooccurrence_anti_pairs, w) for w in (50, 100, 200)),
    *((f"A4_cooc_trip_w{w}", _ad_cooccurrence_triplet, w) for w in (50, 100)),
    *((f"A5_cooc_cond_w{w}", _ad_cooccurrence_conditional, w) for w in (30, 50, 100)),
    *((f"B1_struct_tmpl_w{w}", _ad_structural_template_match, w) for w in (100, 200, 500)),
    *((f"B2_struct_sum_w{w}", _ad_structural_sum_regression, w) for w in (30, 50, 100)),
    *((f"B3_struct_oe_w{w}", _ad_structural_odd_even_transition, w) for w in (50, 100, 200)),
    *((f"B4_struct_gap_w{w}", _ad_structural_gap_pattern, w) for w in (50, 100)),
    *((f"C1_cond_entropy_w{w}", _ad_conditional_entropy_selector, w) for w in (50, 100, 200)),
    *((f"C2_mutual_info_w{w}", _ad_mutual_information_selector, w) for w in (50, 100)),
    *((f"C3_surprise_w{w}", _ad_surprise_selector, w) for w in (50, 100)),
    *((f"D1_neg_elim_w{w}", _ad_negative_elimination, w) for w in (30, 50, 100)),
    ("D2_neg_overdue", _ad_negative_overdue_filter, None),
    *((f"D3_neg_consensus_w{w}", _ad_negative_consensus_remove, w) for w in (20, 30, 50)),
    *((f"E1_zone_trans_w{w}", _ad_zone_transition_markov, w) for w in (50, 100, 200)),
    *((f"E2_zone_consec_w{w}", _ad_zone_consecutive_zone_bet, w) for w in (30, 50, 100)),
    *((f"F1_graph_degree_w{w}", _ad_graph_centrality_bet, w) for w in (50, 100, 200)),
    *((f"F2_graph_bridge_w{w}", _ad_graph_bridge_bet, w) for w in (50, 100)),
    *((f"F3_graph_pagerank_w{w}", _ad_graph_pagerank_bet, w) for w in (50, 100, 200)),
)


class BigLottoAutoDiscoveryAdapter(PortfolioBetAdapter):
    """30 frozen candidate-feature methods (6 dimensions), each swept across
    its own declared window grid -- 54 native tickets in the donor's own
    ``build_methods()`` insertion order."""

    strategy_id = "legacy_biglotto__auto_discovery_biglotto__06bcb164db84"
    strategy_name = "大樂透 Auto-Discovery（6維度x54組態）"  # noqa: RUF001
    strategy_version = "v0.1"
    # A5 (conditional co-occurrence) needs at least one shared number between
    # two consecutive draws in its window to populate a candidate at all;
    # empirically (two unrelated synthetic generators) that is already true
    # by history length 9, but 50 keeps a generous, Wave-1-consistent margin
    # -- the same fail-closed InvalidOutput this framework already raises
    # for any adapter is still the backstop if some pathological real
    # history ever starves every dimension-A5 window regardless.
    min_history = 50
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = len(_AUTO_DISCOVERY_METHODS)

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        tickets: list[tuple[int, ...]] = []
        for _name, func, window in _AUTO_DISCOVERY_METHODS:
            ticket = func(history) if window is None else func(history, window)
            tickets.append(ticket)
        return tuple(tickets)


__all__ = [
    "BigLottoAutoDiscoveryAdapter",
    "BigLottoCoreSatelliteAdapter",
    "BigLottoHighPrizeTrendAdapter",
]
